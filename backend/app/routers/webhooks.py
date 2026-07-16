"""Webhooks da Meta para eventos do Instagram (comentários)."""

import json
import logging

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.security import verify_meta_signature
from app.services.automation_engine import process_comment, process_inbound_message

logger = logging.getLogger("inboxpilot.webhooks")
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/instagram")
async def verify_webhook(
    mode: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    challenge: str = Query("", alias="hub.challenge"),
):
    """Handshake de verificação exigido pela Meta ao registrar o webhook."""
    if mode == "subscribe" and token == settings.webhook_verify_token:
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=status.HTTP_403_FORBIDDEN)


@router.post("/instagram")
async def receive_event(request: Request, db: AsyncSession = Depends(get_session)):
    """Recebe notificações de eventos e dispara automações."""
    raw = await request.body()

    # Segurança: valida a assinatura da Meta (X-Hub-Signature-256).
    if settings.meta_app_secret:
        signature = request.headers.get("X-Hub-Signature-256")
        if not verify_meta_signature(raw, signature, settings.meta_app_secret):
            logger.warning("Assinatura do webhook inválida — rejeitado.")
            return Response(status_code=status.HTTP_403_FORBIDDEN)

    body = json.loads(raw)

    for entry in body.get("entry", []):
        account_id = str(entry.get("id", ""))

        # Comentários (campo "comments") → dispara automações.
        for change in entry.get("changes", []):
            if change.get("field") != "comments":
                continue
            value = change.get("value", {})
            await process_comment(
                db=db,
                account_id=account_id,
                comment_id=str(value.get("id", "")),
                text=value.get("text", ""),
                post_id=(value.get("media") or {}).get("id"),
                from_user=(value.get("from") or {}).get("id"),
                from_username=(value.get("from") or {}).get("username"),
            )

        # Mensagens recebidas (DMs) → registra na conversa.
        for event in entry.get("messaging", []):
            message = event.get("message") or {}
            if message.get("is_echo"):
                continue
            await process_inbound_message(
                db=db,
                account_id=account_id,
                sender_id=(event.get("sender") or {}).get("id", ""),
                text=message.get("text", ""),
                mid=message.get("mid"),
                reply_to=message.get("reply_to"),
                attachments=message.get("attachments"),
            )

    # A Meta espera 200 rápido.
    return {"status": "ok"}
