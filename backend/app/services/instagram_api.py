"""Cliente fino da Graph API da Meta (Instagram)."""

import httpx

from app.core.config import settings

# Fluxo "Instagram API with Instagram Login": host é graph.instagram.com
# (o token IGAA... NÃO funciona em graph.facebook.com).
GRAPH_BASE = "https://graph.instagram.com"


async def exchange_for_long_lived(short_token: str) -> dict:
    """Troca o token curto (~1h) por um de longa duração (~60 dias)."""
    url = f"{GRAPH_BASE}/access_token"
    params = {
        "grant_type": "ig_exchange_token",
        "client_secret": settings.meta_app_secret,
        "access_token": short_token,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()  # { access_token, token_type, expires_in }


async def refresh_long_lived(long_token: str) -> dict:
    """Renova um token de longa duração (válido: >24h de idade e <60 dias)."""
    url = f"{GRAPH_BASE}/refresh_access_token"
    params = {"grant_type": "ig_refresh_token", "access_token": long_token}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()  # { access_token, token_type, expires_in }


async def subscribe_webhooks(ig_user_id: str, access_token: str) -> dict:
    """Inscreve o app nos webhooks da conta (comentários + mensagens)."""
    url = f"{GRAPH_BASE}/{settings.graph_api_version}/{ig_user_id}/subscribed_apps"
    params = {
        "subscribed_fields": "comments,messages",
        "access_token": access_token,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def get_user_profile(igsid: str, access_token: str) -> dict:
    """Perfil de um usuário que interagiu (username, nome, foto). Best-effort.

    Funciona para usuários dentro do contexto de mensagens da conta.
    """
    url = f"{GRAPH_BASE}/{settings.graph_api_version}/{igsid}"
    params = {"fields": "name,username,profile_pic", "access_token": access_token}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def get_subscribed_apps(ig_user_id: str, access_token: str) -> dict:
    """Consulta os campos de webhook aos quais a conta está inscrita."""
    url = f"{GRAPH_BASE}/{settings.graph_api_version}/{ig_user_id}/subscribed_apps"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params={"access_token": access_token})
        resp.raise_for_status()
        return resp.json()


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
    """Busca dados básicos do perfil (id, user_id, username).

    `id` costuma ser o identificador usado nos webhooks (entry.id); `user_id`
    é o usado nas chamadas da Graph API. Podem ser diferentes.
    """
    url = f"{GRAPH_BASE}/{settings.graph_api_version}/me"
    params = {"fields": "id,user_id,username", "access_token": access_token}
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
