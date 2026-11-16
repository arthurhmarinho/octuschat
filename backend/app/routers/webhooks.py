"""Webhooks da Meta para eventos do Instagram (comentários e mensagens)."""

import json
import logging
import time

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.core.database import get_session
from app.core.security import verify_meta_signature
from app.services.webhook_events import extract_events
from app.workers import webhook_worker

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
    """Recebe notificações da Meta: valida, enfileira e responde 200 na hora.

    O processamento (automações, envio de DMs) acontece no worker
    (`app/workers/webhook_worker.py`). Eventos repetidos são descartados pela
    `dedupe_key`. Se não der para gravar, devolve 500 — e a Meta reenvia.
    """
    started = time.monotonic()
    raw = await request.body()

    # Segurança: valida a assinatura da Meta (X-Hub-Signature-256).
    if settings.meta_app_secret:
        signature = request.headers.get("X-Hub-Signature-256")
        if not verify_meta_signature(raw, signature, settings.meta_app_secret):
            logger.warning("Assinatura do webhook inválida — rejeitado.")
            return Response(status_code=status.HTTP_403_FORBIDDEN)

    try:
        body = json.loads(raw)
    except ValueError:
        logger.warning("Webhook com corpo que não é JSON — rejeitado.")
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    events = extract_events(body if isinstance(body, dict) else {})
    inserted = await crud.webhook_event.enqueue(db, events)
    if inserted:
        webhook_worker.notify()
    logger.info(
        "Webhook: %s evento(s), %s novo(s), %s duplicado(s) — %.0f ms.",
        len(events), inserted, len(events) - inserted,
        (time.monotonic() - started) * 1000,
    )
    return {"status": "ok"}
