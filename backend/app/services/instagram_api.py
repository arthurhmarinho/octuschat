"""Cliente fino da Graph API da Meta (Instagram).

Segurança do token:
- vai no header ``Authorization: Bearer`` (nunca na URL), exceto nos
  endpoints de troca/renovação de token, que o exigem como parâmetro;
- erros viram ``InstagramAPIError`` com a mensagem da Meta, sem a URL — o
  ``str()`` de um erro do httpx inclui a URL, que pode conter o token.
"""

import asyncio
import logging

import httpx

from app.core.config import settings
from app.core.security import redact_secrets

logger = logging.getLogger("inboxpilot.ig_api")

# Fluxo "Instagram API with Instagram Login": host é graph.instagram.com
# (o token IGAA... NÃO funciona em graph.facebook.com).
GRAPH_BASE = "https://graph.instagram.com"


class InstagramAPIError(Exception):
    """Falha numa chamada à Graph API. A mensagem nunca contém o token."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(redact_secrets(message))


def _client() -> httpx.AsyncClient:
    """Fábrica do cliente HTTP (ponto único — os testes trocam o transporte)."""
    return httpx.AsyncClient(timeout=15)


def _auth(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def _versioned(path: str) -> str:
    return f"{GRAPH_BASE}/{settings.graph_api_version}/{path}"


def _check(resp: httpx.Response) -> dict:
    """Devolve o JSON ou levanta InstagramAPIError com a mensagem da Meta."""
    if resp.is_success:
        return resp.json()
    detail = ""
    try:
        err = resp.json().get("error") or {}
        detail = err.get("message") or ""
        if err.get("code") is not None:
            detail = f"{detail} (code {err.get('code')}"
            if err.get("error_subcode") is not None:
                detail += f", subcode {err.get('error_subcode')}"
            detail += ")"
    except ValueError:
        detail = resp.text[:300]
    raise InstagramAPIError(
        f"HTTP {resp.status_code}: {detail or resp.reason_phrase}", resp.status_code
    )


async def _request(
    method: str,
    url: str,
    *,
    access_token: str | None = None,
    params: dict | None = None,
    json: dict | None = None,
    retries: int = 0,
) -> dict:
    """Chamada HTTP com retry/backoff opcional.

    Repete em erros de rede/timeout e 5xx; 4xx (permanente) sobe imediatamente.
    """
    headers = _auth(access_token) if access_token else None
    last: InstagramAPIError | None = None
    for attempt in range(retries + 1):
        try:
            async with _client() as client:
                resp = await client.request(
                    method, url, params=params, json=json, headers=headers
                )
            return _check(resp)
        except InstagramAPIError as exc:
            if exc.status_code is not None and exc.status_code < 500:
                raise
            last = exc
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last = InstagramAPIError(f"{type(exc).__name__}: {exc}")
        if attempt < retries:
            await asyncio.sleep(0.5 * (attempt + 1))
            logger.info("Retry %s/%s para %s", attempt + 1, retries, url)
    assert last is not None
    raise last


async def _post(url: str, *, access_token: str, params=None, json=None) -> dict:
    """POST de envio (mensagens/respostas): com retry/backoff."""
    return await _request(
        "POST", url, access_token=access_token, params=params, json=json, retries=2
    )


async def exchange_for_long_lived(short_token: str) -> dict:
    """Troca o token curto (~1h) por um de longa duração (~60 dias).

    Este endpoint exige o token como parâmetro (não aceita header).
    """
    params = {
        "grant_type": "ig_exchange_token",
        "client_secret": settings.meta_app_secret,
        "access_token": short_token,
    }
    # { access_token, token_type, expires_in }
    return await _request("GET", f"{GRAPH_BASE}/access_token", params=params)


async def refresh_long_lived(long_token: str) -> dict:
    """Renova um token de longa duração (válido: >24h de idade e <60 dias).

    Este endpoint exige o token como parâmetro (não aceita header).
    """
    params = {"grant_type": "ig_refresh_token", "access_token": long_token}
    # { access_token, token_type, expires_in }
    return await _request("GET", f"{GRAPH_BASE}/refresh_access_token", params=params)


async def subscribe_webhooks(ig_user_id: str, access_token: str) -> dict:
    """Inscreve o app nos webhooks da conta (comentários + mensagens)."""
    return await _request(
        "POST",
        _versioned(f"{ig_user_id}/subscribed_apps"),
        access_token=access_token,
        params={"subscribed_fields": "comments,messages"},
    )


async def get_user_profile(igsid: str, access_token: str) -> dict:
    """Perfil de um usuário que interagiu (username, nome, foto). Best-effort.

    Funciona para usuários dentro do contexto de mensagens da conta.
    """
    return await _request(
        "GET",
        _versioned(igsid),
        access_token=access_token,
        params={"fields": "name,username,profile_pic"},
    )


async def get_subscribed_apps(ig_user_id: str, access_token: str) -> dict:
    """Consulta os campos de webhook aos quais a conta está inscrita."""
    return await _request(
        "GET", _versioned(f"{ig_user_id}/subscribed_apps"), access_token=access_token
    )


async def reply_publicly_to_comment(
    comment_id: str, message: str, access_token: str
) -> dict:
    """Responde PUBLICAMENTE ao comentário (aparece como reply no post)."""
    return await _post(
        _versioned(f"{comment_id}/replies"),
        access_token=access_token,
        params={"message": message},
    )


def build_message(text: str, buttons: list[dict] | None = None) -> dict:
    """Monta o objeto `message`: texto puro ou button template (até 3 web_url)."""
    if buttons:
        return {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text[:640],
                    "buttons": [
                        {"type": "web_url", "url": b["url"], "title": b["label"][:20]}
                        for b in buttons[:3]
                    ],
                },
            }
        }
    return {"text": text}


async def reply_privately_to_comment(
    ig_user_id: str,
    comment_id: str,
    text: str,
    access_token: str,
    buttons: list[dict] | None = None,
) -> dict:
    """Resposta privada (private reply) a um comentário → vira DM.

    Esta é a rota correta para o caso 'comentou no post → recebe DM'.
    A Meta permite UMA resposta privada por comentário.
    """
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": build_message(text, buttons),
    }
    return await _post(
        _versioned(f"{ig_user_id}/messages"), access_token=access_token, json=payload
    )


async def send_message_to_user(
    ig_user_id: str,
    recipient_id: str,
    text: str,
    access_token: str,
    buttons: list[dict] | None = None,
) -> dict:
    """Envia mensagem regular ao usuário (dentro da janela de 24h)."""
    payload = {
        "recipient": {"id": recipient_id},
        "message": build_message(text, buttons),
    }
    return await _post(
        _versioned(f"{ig_user_id}/messages"), access_token=access_token, json=payload
    )


async def get_profile(ig_user_id: str, access_token: str) -> dict:
    """Busca dados básicos do perfil (id, user_id, username).

    `id` costuma ser o identificador usado nos webhooks (entry.id); `user_id`
    é o usado nas chamadas da Graph API. Podem ser diferentes.
    """
    return await _request(
        "GET",
        _versioned("me"),
        access_token=access_token,
        params={"fields": "id,user_id,username"},
    )


async def list_media(
    ig_user_id: str, access_token: str, limit: int = 24
) -> list[dict]:
    """Lista as publicações/Reels da conta (para o seletor de post)."""
    data = await _request(
        "GET",
        _versioned(f"{ig_user_id}/media"),
        access_token=access_token,
        params={
            "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp",
            "limit": limit,
        },
    )
    return data.get("data", [])
