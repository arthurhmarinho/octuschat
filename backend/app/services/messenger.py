"""Ponto central de envio de mensagens ao contato.

Toda mensagem automática passa por aqui:
- `send_private_reply`: o PRIMEIRO envio de um gatilho de comentário (a Meta
  permite uma private reply por comentário). Não depende da janela de 24h.
- `send_dm`: qualquer outro envio (Send API). Só sai com a janela de 24h
  aberta — última mensagem RECEBIDA do contato por DM (`last_inbound_at`).
  A doc da Meta: depois de uma private reply, só dá para mandar mais se o
  contato responder.

A gravação no histórico (`messages`) fica no engine.
"""

import logging
from datetime import datetime, timedelta, timezone

from app.models.contact import Contact
from app.services import instagram_api

logger = logging.getLogger("inboxpilot.messenger")

WINDOW = timedelta(hours=24)


class OutsideWindow(Exception):
    """Envio recusado: o contato não mandou DM nas últimas 24h."""


def window_open(contact: Contact, now: datetime | None = None) -> bool:
    """True se o contato mandou DM nas últimas 24h."""
    last = contact.last_inbound_at
    if last is None:
        return False
    now = now or datetime.now(timezone.utc)
    return now - last < WINDOW


def embed_buttons(text: str, buttons: list[dict] | None) -> str:
    """Texto com os links dos botões embutidos (quando o template não serve)."""
    links = [b for b in (buttons or []) if (b.get("type") or "web_url") == "web_url"]
    if not links:
        return text
    lines = "\n".join(f"👉 {b['label']}: {b['url']}" for b in links)
    return f"{text}\n\n{lines}" if text else lines


async def send_private_reply(
    ig_user_id: str, comment_id: str, text: str, buttons: list[dict] | None, token: str
) -> str:
    """Envia a private reply e devolve o texto efetivamente enviado.

    Tenta o button template; se a Meta recusar, cai para uma private reply só
    de texto com os links embutidos (a única private reply do comentário ainda
    não foi gasta, porque a primeira falhou). Erro no fallback sobe.
    """
    if not buttons:
        await instagram_api.reply_privately_to_comment(
            ig_user_id=ig_user_id, comment_id=comment_id, text=text, access_token=token
        )
        return text
    try:
        await instagram_api.reply_privately_to_comment(
            ig_user_id=ig_user_id, comment_id=comment_id, text=text,
            access_token=token, buttons=buttons,
        )
        return text
    except Exception as exc:  # noqa: BLE001
        logger.warning("Private reply com botões falhou (%s); enviando só texto.", exc)
    body = embed_buttons(text, buttons)
    await instagram_api.reply_privately_to_comment(
        ig_user_id=ig_user_id, comment_id=comment_id, text=body, access_token=token
    )
    return body


async def send_dm(
    ig_user_id: str,
    contact: Contact,
    text: str,
    buttons: list[dict] | None,
    token: str,
    now: datetime | None = None,
) -> None:
    """Envia pela Send API, só com a janela de 24h aberta."""
    if not window_open(contact, now):
        raise OutsideWindow(
            f"contato {contact.ig_user_id} sem DM nas últimas 24h"
        )
    await instagram_api.send_message_to_user(
        ig_user_id, contact.ig_user_id, text, token, buttons
    )


async def send_private_reply_quick_replies(
    ig_user_id: str, comment_id: str, text: str, replies: list[dict], token: str
) -> bool:
    """Private reply com respostas rápidas. Devolve True se saiu com elas.

    A Meta pode recusar `quick_replies` numa private reply [não verificado — testar
    ao vivo]. Nesse caso (erro 4xx que não seja token inválido) cai para uma
    private reply só de texto: a única do comentário ainda não foi gasta. Devolve
    False e o chamador registra `quick_replies_unsupported_in_private_reply`.
    Erro de token (190), de rede ou 5xx sobe: não dá para saber se saiu.
    """
    try:
        await instagram_api.send_quick_replies(
            ig_user_id, {"comment_id": comment_id}, text, replies, token
        )
        return True
    except instagram_api.InstagramAPIError as exc:
        transient = exc.status_code is None or exc.status_code >= 500
        if transient or exc.code == 190:
            raise
        logger.warning("Private reply com respostas rápidas recusada (%s); enviando só texto.", exc)
    await instagram_api.reply_privately_to_comment(
        ig_user_id=ig_user_id, comment_id=comment_id, text=text, access_token=token
    )
    return False


async def send_dm_quick_replies(
    ig_user_id: str,
    contact: Contact,
    text: str,
    replies: list[dict],
    token: str,
    now: datetime | None = None,
) -> None:
    """Texto com respostas rápidas pela Send API, só com a janela aberta."""
    if not window_open(contact, now):
        raise OutsideWindow(f"contato {contact.ig_user_id} sem DM nas últimas 24h")
    await instagram_api.send_quick_replies(
        ig_user_id, {"id": contact.ig_user_id}, text, replies, token
    )


async def send_dm_image(
    ig_user_id: str, contact: Contact, url: str, token: str, now: datetime | None = None
) -> None:
    """Imagem pela Send API, só com a janela aberta."""
    if not window_open(contact, now):
        raise OutsideWindow(f"contato {contact.ig_user_id} sem DM nas últimas 24h")
    await instagram_api.send_image(ig_user_id, contact.ig_user_id, url, token)
