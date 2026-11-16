"""Tradução do corpo do webhook da Meta em eventos de fila, e o despacho deles.

- `extract_events` é PURA: corpo do webhook → linhas para `webhook_events`.
- `dispatch` chama o engine com os dados do evento e o limitador de envios
  do worker.
"""

import hashlib
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.automation_engine import process_comment, process_inbound_message
from app.services.send_limiter import SendLimiter

logger = logging.getLogger("inboxpilot.webhook_events")

COMMENT = "comment"
MESSAGE = "message"


def _hash_key(prefix: str, account_id: str, item: dict) -> str:
    raw = json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(f"{account_id}|{raw}".encode()).hexdigest()
    return f"{prefix}:sha256:{digest}"


def extract_events(body: dict) -> list[dict]:
    """Quebra o corpo do webhook em eventos (um por comentário/mensagem).

    Mesmos filtros de antes da fila: só `changes` do campo "comments"; em
    `messaging`, ignora ecos da própria conta e eventos sem `message`
    (leitura, entrega…), que o engine já descartava.
    """
    events: list[dict] = []
    for entry in body.get("entry") or []:
        account_id = str(entry.get("id", ""))

        for change in entry.get("changes") or []:
            if change.get("field") != "comments":
                continue
            value = change.get("value") or {}
            comment_id = value.get("id")
            key = (
                f"comment:{comment_id}"
                if comment_id
                else _hash_key(COMMENT, account_id, value)
            )
            events.append(
                {
                    "dedupe_key": key,
                    "account_id": account_id,
                    "kind": COMMENT,
                    "payload": {"value": value},
                }
            )

        for item in entry.get("messaging") or []:
            message = item.get("message")
            if not message or message.get("is_echo"):
                continue
            mid = message.get("mid")
            key = f"mid:{mid}" if mid else _hash_key(MESSAGE, account_id, item)
            events.append(
                {
                    "dedupe_key": key,
                    "account_id": account_id,
                    "kind": MESSAGE,
                    "payload": {"event": item},
                }
            )
    return events


async def dispatch(
    db: AsyncSession,
    kind: str,
    account_id: str,
    payload: dict,
    limiter: SendLimiter | None = None,
) -> None:
    """Executa um evento da fila no engine de automações.

    Pode levantar `SendDeferred` (antes de enviar qualquer coisa) se o
    limitador mandar esperar.
    """
    if kind == COMMENT:
        value = payload.get("value") or {}
        await process_comment(
            db=db,
            account_id=account_id,
            comment_id=str(value.get("id", "")),
            text=value.get("text", ""),
            post_id=(value.get("media") or {}).get("id"),
            from_user=(value.get("from") or {}).get("id"),
            from_username=(value.get("from") or {}).get("username"),
            limiter=limiter,
        )
    elif kind == MESSAGE:
        event = payload.get("event") or {}
        message = event.get("message") or {}
        await process_inbound_message(
            db=db,
            account_id=account_id,
            sender_id=(event.get("sender") or {}).get("id", ""),
            text=message.get("text", ""),
            mid=message.get("mid"),
            reply_to=message.get("reply_to"),
            attachments=message.get("attachments"),
            limiter=limiter,
        )
    else:
        logger.warning("Evento de tipo desconhecido na fila: %s (ignorado)", kind)
