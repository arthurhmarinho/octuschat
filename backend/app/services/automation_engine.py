"""Motor de automação: avalia um comentário e dispara as respostas.

Concentra a lógica de negócio que liga 'evento de comentário' →
'automações que casam' → 'envio de DM', com idempotência via MessageLog.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.account import InstagramAccount
from app.models.contact import Contact
from app.models.message_log import MessageLog
from app.services import instagram_api, token_service
from app.services.instagram_api import reply_privately_to_comment

logger = logging.getLogger("inboxpilot.engine")


async def _enrich_contact(
    db: AsyncSession, account: InstagramAccount, contact: Contact
) -> None:
    """Preenche foto (e username, se faltar) do contato via API. Best-effort."""
    if contact.profile_pic and contact.username:
        return
    try:
        prof = await instagram_api.get_user_profile(
            contact.ig_user_id, account.access_token
        )
        await crud.contact.upsert(
            db,
            account.ig_user_id,
            contact.ig_user_id,
            username=prof.get("username") or contact.username,
            profile_pic=prof.get("profile_pic"),
            touch=False,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("Sem perfil enriquecido p/ %s: %s", contact.ig_user_id, exc)


def compose_message(
    text: str, link_url: str | None, link_label: str | None
) -> str:
    """Monta o corpo da DM a partir de texto + link opcional.

    A private reply da Meta envia apenas texto, então embutimos a URL no
    final. O frontend espelha esta mesma lógica no preview ao vivo.
    """
    if not link_url:
        return text
    if link_label:
        return f"{text}\n\n👉 {link_label}: {link_url}"
    return f"{text}\n\n{link_url}"


def _store_body(text: str, buttons: list | None) -> str:
    """Texto como fica gravado na conversa (anexa botões de forma legível)."""
    stored = text
    if buttons:
        stored += "\n\n" + "\n".join(f"[{b['label']}] → {b['url']}" for b in buttons)
    return stored


async def _send_followups(
    db: AsyncSession,
    account: InstagramAccount,
    auto,
    contact: Contact,
    recipient_id: str,
    source: str,
) -> None:
    """Envia os passos extras do flow (mensagens 2..N) em sequência via DM.

    A janela de 24h já está aberta pela mensagem 1, então todos os passos usam
    ``send_message_to_user``. Se um passo falha, interrompe a sequência.
    """
    for step in auto.flow or []:
        text = (step.get("text") or "").strip()
        buttons = step.get("buttons") or None
        if not text and not buttons:
            continue
        try:
            await instagram_api.send_message_to_user(
                account.ig_user_id, recipient_id, text, account.access_token, buttons
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha em passo do flow de '%s': %s", auto.name, exc)
            break
        await crud.message.create(
            db, account.ig_user_id, contact.id, "out", _store_body(text, buttons), source
        )


async def process_comment(
    db: AsyncSession,
    account_id: str,
    comment_id: str,
    text: str,
    post_id: str | None,
    from_user: str | None,
    from_username: str | None = None,
) -> None:
    """Processa um comentário recebido via webhook."""
    # Idempotência: se já respondemos este comentário, ignora.
    if await crud.message_log.exists_for_comment(db, comment_id):
        logger.info("Comentário %s já processado, ignorando.", comment_id)
        return

    # O webhook identifica a conta por ig_id (≠ ig_user_id); casa por qualquer um.
    account = await crud.account.get_by_any_id(db, account_id)
    if account is None:
        logger.warning("Conta %s não conectada; nada a fazer.", account_id)
        return
    account = await token_service.ensure_fresh(db, account)
    # Canoniza para o ig_user_id (chave das automações/contatos, usada no front).
    account_id = account.ig_user_id

    # Vincula automações "próxima publicação" se este comentário é de um post novo.
    if post_id:
        await crud.automation.bind_next_posts(db, account_id, post_id)

    matches = await crud.automation.find_matching(db, account_id, text, post_id)
    if not matches:
        return

    # Dispara a primeira automação que casou (1 resposta privada por comentário).
    auto = matches[0]
    buttons = auto.buttons or None
    # Com botões, o texto é a mensagem crua (o link vira botão); sem botões,
    # embutimos o link no texto (compat com automações antigas).
    body = auto.reply_message if buttons else compose_message(
        auto.reply_message, auto.link_url, auto.link_label
    )
    log = MessageLog(
        automation_id=auto.id,
        comment_id=comment_id,
        recipient_id=from_user,
        status="sent",
    )
    try:
        # Tenta a private reply já com os botões (1 mensagem).
        await reply_privately_to_comment(
            ig_user_id=account.ig_user_id,
            comment_id=comment_id,
            text=body,
            access_token=account.access_token,
            buttons=buttons,
        )
        logger.info("Automação '%s' disparada para %s.", auto.name, from_user)
    except Exception as exc:  # noqa: BLE001
        # Fallback: se o template foi recusado na private reply, garante o texto
        # e manda os botões como mensagem regular (a janela de 24h está aberta).
        logger.warning("Private reply com botões falhou (%s); tentando fallback.", exc)
        try:
            await reply_privately_to_comment(
                ig_user_id=account.ig_user_id,
                comment_id=comment_id,
                text=body,
                access_token=account.access_token,
            )
            if buttons and from_user:
                await instagram_api.send_message_to_user(
                    account.ig_user_id, from_user, body, account.access_token, buttons
                )
            logger.info("Fallback OK para '%s'.", auto.name)
        except Exception as exc2:  # noqa: BLE001
            log.status = "failed"
            log.error = str(exc2)
            logger.exception("Falha ao enviar (mesmo no fallback): %s", exc2)

    # Resposta PÚBLICA opcional no comentário (best-effort, não bloqueia a DM).
    if auto.public_reply:
        try:
            await instagram_api.reply_publicly_to_comment(
                comment_id, auto.public_reply, account.access_token
            )
            logger.info("Resposta pública enviada no comentário %s.", comment_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha na resposta pública: %s", exc)

    db.add(log)
    await db.commit()

    # Registra contato + mensagem de saída (alimenta Conversas/Contatos).
    if log.status == "sent" and from_user:
        contact = await crud.contact.upsert(
            db, account_id, from_user, username=from_username
        )
        await _enrich_contact(db, account, contact)
        await crud.message.create(
            db, account_id, contact.id, "out", _store_body(body, buttons), "comment_reply"
        )
        # Mensagens seguintes do flow (Fase 3), em sequência.
        await _send_followups(db, account, auto, contact, from_user, "comment_reply")


async def process_inbound_message(
    db: AsyncSession,
    account_id: str,
    sender_id: str,
    text: str,
    mid: str | None = None,
    reply_to: dict | None = None,
    attachments: list | None = None,
) -> None:
    """Registra a mensagem recebida e, se casar um gatilho, responde.

    Distingue o tipo pelo payload do webhook:
    - anexo ``story_mention`` → gatilho de menção em story (sem texto/keyword);
    - ``reply_to.story`` → resposta a um story (keyword opcional);
    - caso contrário → DM comum.
    """
    if not sender_id:
        return
    attachments = attachments or []
    is_story_mention = any(
        (a or {}).get("type") == "story_mention" for a in attachments
    )
    # Menção em story costuma vir sem texto; demais fluxos exigem texto.
    if not text and not is_story_mention:
        return

    account = await crud.account.get_by_any_id(db, account_id)
    if account is None:
        return
    account_id = account.ig_user_id  # canoniza
    # Ignora eco das mensagens enviadas pela própria conta.
    if sender_id in (account_id, account.ig_id):
        return

    is_story_reply = bool((reply_to or {}).get("story")) and not is_story_mention
    if is_story_mention:
        source, kind = "story_mention", "Menção em story"
    elif is_story_reply:
        source, kind = "story_reply", "Resposta a story"
    else:
        source, kind = "dm", "Mensagem"
    # Menção sem texto: registra um marcador legível na conversa.
    inbound_text = text or "📸 Mencionou você em um story"

    contact = await crud.contact.upsert(db, account_id, sender_id)
    await _enrich_contact(db, account, contact)
    await crud.message.create(db, account_id, contact.id, "in", inbound_text, source)
    logger.info("%s recebida de %s registrada.", kind, sender_id)

    # Gatilhos: cada tipo tem seu matcher.
    if mid and await crud.message_log.exists_for_comment(db, mid):
        return  # idempotência: já respondemos esta mensagem
    if is_story_mention:
        matches = await crud.automation.find_matching_story_mention(db, account_id)
    elif is_story_reply:
        matches = await crud.automation.find_matching_story(db, account_id, text)
    else:
        matches = await crud.automation.find_matching_dm(db, account_id, text)
    if not matches:
        return

    account = await token_service.ensure_fresh(db, account)
    auto = matches[0]
    buttons = auto.buttons or None
    body = auto.reply_message if buttons else compose_message(
        auto.reply_message, auto.link_url, auto.link_label
    )
    log = MessageLog(
        automation_id=auto.id,
        comment_id=mid or f"dm:{sender_id}:{contact.id}",
        recipient_id=sender_id,
        status="sent",
    )
    try:
        await instagram_api.send_message_to_user(
            account.ig_user_id, sender_id, body, account.access_token, buttons
        )
        logger.info("Automação de DM '%s' disparada para %s.", auto.name, sender_id)
    except Exception as exc:  # noqa: BLE001
        log.status = "failed"
        log.error = str(exc)
        logger.exception("Falha ao responder DM: %s", exc)
    db.add(log)
    await db.commit()

    if log.status == "sent":
        await crud.message.create(
            db, account_id, contact.id, "out", _store_body(body, buttons), source
        )
        # Mensagens seguintes do flow (Fase 3), em sequência.
        await _send_followups(db, account, auto, contact, sender_id, source)
