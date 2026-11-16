"""Motor de automação: evento → automação que casa → execução do grafo.

Todos os gatilhos (comentário, DM, story) executam o grafo da automação por
um único caminho (`_plan` + `_run_graph`):

1. o grafo é resolvido por `flow_runner.plan_steps` (função pura);
2. o limitador da conta recebe o número de envios previstos — se mandar
   esperar, nada é enviado e o evento volta para a fila (`SendDeferred`);
3. o 1º envio de um comentário é a private reply; os demais saem pela Send
   API via `messenger.send_dm`, que exige a janela de 24h aberta.

Idempotência: `message_logs` (um registro por comentário/mid).
"""

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.security import redact_secrets
from app.models.account import InstagramAccount
from app.models.contact import Contact
from app.models.message_log import MessageLog
from app.services import flow_runner, instagram_api, messenger, token_service
from app.services.send_limiter import NoLimit, SendDeferred, SendLimiter

logger = logging.getLogger("inboxpilot.engine")


async def _enrich_contact(
    db: AsyncSession, account: InstagramAccount, contact: Contact, token: str
) -> None:
    """Preenche foto (e username, se faltar) do contato via API. Best-effort."""
    if contact.profile_pic and contact.username:
        return
    try:
        prof = await instagram_api.get_user_profile(contact.ig_user_id, token)
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


def _store_body(text: str, buttons: list | None) -> str:
    """Texto como fica gravado na conversa (anexa botões de forma legível)."""
    stored = text
    if buttons:
        stored += "\n\n" + "\n".join(
            f"[{b['label']}] → {b['url']}" for b in buttons if b.get("url")
        )
    return stored


@dataclass
class RunResult:
    first_sent: bool = False
    error: str | None = None
    sent: int = 0


async def _plan(
    limiter: SendLimiter,
    account_id: str,
    graph: dict,
    context: dict,
    *,
    private_reply: bool,
    window_open: bool,
) -> list[dict]:
    """Planeja os envios e reserva no limitador ANTES de qualquer efeito.

    Levanta SendDeferred se o limitador mandar esperar.
    """
    steps = flow_runner.plan_steps(graph, context)
    if private_reply and not window_open:
        planned = min(len(steps), 1)  # sem janela, só a private reply sai
    else:
        planned = len(steps)
    if planned:
        delay = await limiter.reserve(
            account_id, sends=planned, private_replies=1 if private_reply else 0
        )
        if delay:
            raise SendDeferred(delay)
    return steps


async def _run_graph(
    db: AsyncSession,
    account: InstagramAccount,
    auto,
    steps: list[dict],
    token: str,
    *,
    contact: Contact | None,
    source: str,
    comment_id: str | None = None,
) -> RunResult:
    """Envia os passos planejados, em ordem, e grava cada um na conversa.

    Com `comment_id`, o 1º passo vai como private reply (com fallback para
    texto + links). Os demais exigem contato e janela de 24h; fora da janela,
    o flow para (com estado de execução, passará a esperar a resposta).
    """
    result = RunResult()
    for i, step in enumerate(steps):
        text, buttons = step["text"], step["buttons"]
        body = _store_body(text, buttons)
        try:
            if i == 0 and comment_id:
                sent_text = await messenger.send_private_reply(
                    account.ig_user_id, comment_id, text, buttons, token
                )
                if sent_text != text:  # caiu no fallback (links embutidos)
                    body = sent_text
            else:
                if contact is None:
                    break
                await messenger.send_dm(account.ig_user_id, contact, text, buttons, token)
        except messenger.OutsideWindow as exc:
            logger.info("Flow de '%s' parou no passo %s: %s", auto.name, i + 1, exc)
            break
        except Exception as exc:  # noqa: BLE001
            if i == 0:
                result.error = redact_secrets(str(exc))
                logger.exception("Falha ao enviar a mensagem 1 de '%s': %s", auto.name, exc)
            else:
                logger.warning("Falha no passo %s do flow de '%s': %s", i + 1, auto.name, exc)
            break
        if i == 0:
            result.first_sent = True
        result.sent += 1
        if contact is not None:
            await crud.message.create(
                db, account.ig_user_id, contact.id, "out", body, source
            )
    return result


async def process_comment(
    db: AsyncSession,
    account_id: str,
    comment_id: str,
    text: str,
    post_id: str | None,
    from_user: str | None,
    from_username: str | None = None,
    limiter: SendLimiter | None = None,
) -> None:
    """Processa um comentário recebido via webhook."""
    limiter = limiter or NoLimit()
    # Idempotência: se já respondemos este comentário, ignora.
    if await crud.message_log.exists_for_comment(db, comment_id):
        logger.info("Comentário %s já processado, ignorando.", comment_id)
        return

    # O webhook identifica a conta por ig_id (≠ ig_user_id); casa por qualquer um.
    account = await crud.account.get_by_any_id(db, account_id)
    if account is None:
        logger.warning("Conta %s não conectada; nada a fazer.", account_id)
        return
    token = await token_service.get_valid_token(db, account)
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
    existing = await crud.contact.find(db, account_id, from_user) if from_user else None
    context = {"text": text, "is_new_contact": existing is None}
    steps = await _plan(
        limiter, account_id, auto.graph, context,
        private_reply=True,
        window_open=existing is not None and messenger.window_open(existing),
    )
    if not steps:
        logger.warning("Automação '%s' sem mensagens para enviar.", auto.name)
        return

    contact = None
    if from_user:
        contact = await crud.contact.upsert(db, account_id, from_user, username=from_username)
        await _enrich_contact(db, account, contact, token)

    result = await _run_graph(
        db, account, auto, steps, token,
        contact=contact, source="comment_reply", comment_id=comment_id,
    )
    if result.first_sent:
        logger.info("Automação '%s' disparada para %s.", auto.name, from_user)

    # Resposta PÚBLICA opcional no comentário (best-effort, não bloqueia a DM).
    if auto.public_reply:
        try:
            await instagram_api.reply_publicly_to_comment(
                comment_id, auto.public_reply, token
            )
            logger.info("Resposta pública enviada no comentário %s.", comment_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha na resposta pública: %s", exc)

    db.add(
        MessageLog(
            automation_id=auto.id,
            comment_id=comment_id,
            recipient_id=from_user,
            status="sent" if result.first_sent else "failed",
            error=result.error,
        )
    )
    await db.commit()


async def process_inbound_message(
    db: AsyncSession,
    account_id: str,
    sender_id: str,
    text: str,
    mid: str | None = None,
    reply_to: dict | None = None,
    attachments: list | None = None,
    limiter: SendLimiter | None = None,
) -> None:
    """Registra a mensagem recebida e, se casar um gatilho, responde.

    Distingue o tipo pelo payload do webhook:
    - anexo ``story_mention`` → gatilho de menção em story (sem texto/keyword);
    - ``reply_to.story`` → resposta a um story (keyword opcional);
    - caso contrário → DM comum.
    """
    limiter = limiter or NoLimit()
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

    # Decide (sem efeitos) se algo vai disparar — o limitador pode adiar o
    # evento, e aí ele é reprocessado do zero.
    already = bool(mid) and await crud.message_log.exists_for_comment(db, mid)
    auto, steps = None, []
    if not already:
        if is_story_mention:
            matches = await crud.automation.find_matching_story_mention(db, account_id)
        elif is_story_reply:
            matches = await crud.automation.find_matching_story(db, account_id, text)
        else:
            matches = await crud.automation.find_matching_dm(db, account_id, text)
        if matches:
            auto = matches[0]
            is_new = not await crud.contact.exists(db, account_id, sender_id)
            # A mensagem que acabou de chegar abre a janela de 24h.
            steps = await _plan(
                limiter, account_id, auto.graph,
                {"text": text, "is_new_contact": is_new},
                private_reply=False, window_open=True,
            )

    contact = await crud.contact.upsert(db, account_id, sender_id, inbound=True)
    await _enrich_contact(db, account, contact, token_service.read_token(account))
    await crud.message.create(db, account_id, contact.id, "in", inbound_text, source)
    logger.info("%s recebida de %s registrada.", kind, sender_id)

    if auto is None or not steps:
        return
    token = await token_service.get_valid_token(db, account)
    result = await _run_graph(
        db, account, auto, steps, token, contact=contact, source=source
    )
    if result.first_sent:
        logger.info("Automação de DM '%s' disparada para %s.", auto.name, sender_id)
    db.add(
        MessageLog(
            automation_id=auto.id,
            comment_id=mid or f"dm:{sender_id}:{contact.id}",
            recipient_id=sender_id,
            status="sent" if result.first_sent else "failed",
            error=result.error,
        )
    )
    await db.commit()
