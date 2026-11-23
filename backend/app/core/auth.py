"""Autenticação da API: segredo compartilhado com o proxy do Next.

O browser nunca fala direto com o backend. O route handler do Next
(`/api/backend/*`) valida a sessão do usuário e injeta o header
`X-Octus-Secret` server-side, junto com `X-Octus-User` (o id do usuário da
sessão). Aqui conferimos o segredo e carregamos o usuário. O `X-Octus-User` só
vale com um segredo válido, e o segredo só o proxy tem.
"""

import hashlib
import hmac
import secrets
import time

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.models.user import User

SECRET_HEADER = "X-Octus-Secret"
USER_HEADER = "X-Octus-User"

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


async def current_user(
    db: AsyncSession = Depends(get_session),
    x_octus_secret: str | None = Header(default=None, alias=SECRET_HEADER),
    x_octus_user: str | None = Header(default=None, alias=USER_HEADER),
) -> User:
    """Dependency: segredo válido + usuário existente. Tudo é 401 genérico."""
    await require_api_secret(x_octus_secret)
    if not x_octus_user or not x_octus_user.isascii() or not x_octus_user.isdigit():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autorizado")
    user = await db.get(User, int(x_octus_user))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Não autorizado")
    return user


def _state_sig(payload: str) -> str:
    key = f"oauth-state:{settings.api_secret}".encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def make_oauth_state(user_id: int, now: float | None = None) -> str:
    """`state` assinado para o OAuth: `<ts>.<nonce>.<uid>.<hmac>`.

    O uid vai dentro da assinatura: o callback (público) sabe QUEM iniciou a
    conexão sem confiar em nada que venha do browser.
    """
    ts = str(int(now if now is not None else time.time()))
    payload = f"{ts}.{secrets.token_urlsafe(16)}.{int(user_id)}"
    return f"{payload}.{_state_sig(payload)}"


def verify_oauth_state(state: str, now: float | None = None) -> int | None:
    """Confere assinatura e validade do `state`; devolve o uid ou None.

    O formato antigo (3 partes, sem uid) é recusado.
    """
    if not settings.api_secret or not state or state.count(".") != 3:
        return None
    ts, nonce, uid, sig = state.split(".")
    if not hmac.compare_digest(sig, _state_sig(f"{ts}.{nonce}.{uid}")):
        return None
    try:
        age = (now if now is not None else time.time()) - int(ts)
        user_id = int(uid)
    except ValueError:
        return None
    if not 0 <= age <= OAUTH_STATE_TTL:
        return None
    return user_id
