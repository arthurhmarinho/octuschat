"""Cliente fino da Graph API da Meta (Instagram)."""

import httpx

from app.core.config import settings

# Fluxo "Instagram API with Instagram Login": host é graph.instagram.com
# (o token IGAA... NÃO funciona em graph.facebook.com).
GRAPH_BASE = "https://graph.instagram.com"


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


async def get_profile(ig_user_id: str, access_token: str) -> dict:
    """Busca dados básicos do perfil (user_id, username)."""
    url = f"{GRAPH_BASE}/{settings.graph_api_version}/me"
    params = {"fields": "user_id,username", "access_token": access_token}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def list_media(
    ig_user_id: str, access_token: str, limit: int = 24
) -> list[dict]:
    """Lista as publicações/Reels da conta (para o seletor de post).

    NÃO testado contra a Meta real ainda (precisa de token válido). Quando o
    Instagram estiver conectado, alimenta a grade visual do builder.
    """
    url = f"{GRAPH_BASE}/{settings.graph_api_version}/{ig_user_id}/media"
    params = {
        "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp",
        "limit": limit,
        "access_token": access_token,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])


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
