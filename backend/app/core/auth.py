"""Autenticação da API: segredo compartilhado com o proxy do Next.

O browser nunca fala direto com o backend. O route handler do Next
(`/api/backend/*`) valida a sessão do usuário e injeta o header
`X-Octus-Secret` server-side. Aqui só conferimos esse segredo.
"""

import hashlib
import hmac
import secrets
import time

from fastapi import Header, HTTPException, status

from app.core.config import settings

SECRET_HEADER = "X-Octus-Secret"

# Validade do `state` do OAuth (ida e volta pela tela da Meta).
OAUTH_STATE_TTL = 15 * 60


async def require_api_secret(
    x_octus_secret: str | None = Header(default=None, alias=SECRET_HEADER),
) -> None:
    """Dependency: exige o segredo da API. Falha fechada se não configurado."""
    expected = settings.api_secret
    if not expected or not x_octus_secret or not hmac.compare_digest(
        x_octus_secret.encode(), expected.encode()
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autorizado")


def _state_sig(payload: str) -> str:
    key = f"oauth-state:{settings.api_secret}".encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def make_oauth_state(now: float | None = None) -> str:
    """`state` assinado para o OAuth: `<ts>.<nonce>.<hmac>`."""
    ts = str(int(now if now is not None else time.time()))
    payload = f"{ts}.{secrets.token_urlsafe(16)}"
    return f"{payload}.{_state_sig(payload)}"


def verify_oauth_state(state: str, now: float | None = None) -> bool:
    """Confere assinatura e validade do `state` devolvido pela Meta."""
    if not settings.api_secret or not state or state.count(".") != 2:
        return False
    ts, nonce, sig = state.split(".")
    if not hmac.compare_digest(sig, _state_sig(f"{ts}.{nonce}")):
        return False
    try:
        age = (now if now is not None else time.time()) - int(ts)
    except ValueError:
        return False
    return 0 <= age <= OAUTH_STATE_TTL
