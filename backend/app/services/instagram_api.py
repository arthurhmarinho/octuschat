"""Cliente fino da Graph API da Meta (Instagram)."""

import httpx

from app.core.config import settings

GRAPH_BASE = "https://graph.facebook.com"


async def reply_privately_to_comment(
    ig_user_id: str, comment_id: str, text: str, access_token: str
) -> dict:
    """Resposta privada (private reply) a um comentário → vira DM.

    Esta é a rota correta para o caso 'comentou no post → recebe DM'.
    A Meta permite UMA resposta privada por comentário.
    """
    url = f"{GRAPH_BASE}/{settings.graph_api_version}/{ig_user_id}/messages"
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {"text": text},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url, params={"access_token": access_token}, json=payload
        )
        resp.raise_for_status()
        return resp.json()


async def send_direct_message(
    ig_user_id: str, recipient_id: str, text: str, access_token: str
) -> dict:
    """Envia DM direta a um usuário (dentro da janela de mensagem permitida)."""
    url = f"{GRAPH_BASE}/{settings.graph_api_version}/{ig_user_id}/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            url, params={"access_token": access_token}, json=payload
        )
        resp.raise_for_status()
        return resp.json()
