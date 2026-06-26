"""Webhooks da Meta para eventos do Instagram (comentários)."""

import logging

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.services.automation_engine import process_comment

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
    body = await request.json()
    logger.info("Webhook recebido: %s", body)

    for entry in body.get("entry", []):
        account_id = str(entry.get("id", ""))
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
            )

    # A Meta espera 200 rápido.
    return {"status": "ok"}
