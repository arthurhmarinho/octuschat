"""Motor de automação: avalia um comentário e dispara as respostas.

Concentra a lógica de negócio que liga 'evento de comentário' →
'automações que casam' → 'envio de DM', com idempotência via MessageLog.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.message_log import MessageLog
from app.services.instagram_api import reply_privately_to_comment

logger = logging.getLogger("inboxpilot.engine")


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


async def process_comment(
    db: AsyncSession,
    account_id: str,
    comment_id: str,
    text: str,
    post_id: str | None,
    from_user: str | None,
) -> None:
    """Processa um comentário recebido via webhook."""
    # Idempotência: se já respondemos este comentário, ignora.
    if await crud.message_log.exists_for_comment(db, comment_id):
        logger.info("Comentário %s já processado, ignorando.", comment_id)
        return

    account = await crud.account.get(db, account_id)
    if account is None:
        logger.warning("Conta %s não conectada; nada a fazer.", account_id)
        return

    matches = await crud.automation.find_matching(db, account_id, text, post_id)
    if not matches:
        return

    # Dispara a primeira automação que casou (1 resposta privada por comentário).
    auto = matches[0]
    log = MessageLog(
        automation_id=auto.id,
        comment_id=comment_id,
        recipient_id=from_user,
        status="sent",
    )
    try:
        await reply_privately_to_comment(
            ig_user_id=account.ig_user_id,
            comment_id=comment_id,
            text=compose_message(auto.reply_message, auto.link_url, auto.link_label),
            access_token=account.access_token,
        )
        logger.info("Automação '%s' disparada para %s.", auto.name, from_user)
    except Exception as exc:  # noqa: BLE001
        log.status = "failed"
        log.error = str(exc)
        logger.exception("Falha ao enviar resposta privada: %s", exc)

    db.add(log)
    await db.commit()
