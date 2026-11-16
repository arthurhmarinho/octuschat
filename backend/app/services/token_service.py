"""Ciclo de vida do token de acesso da conta (cifrado em repouso).

Único lugar que cifra/decifra o token: o banco guarda só
`access_token_enc` (Fernet, ver core/crypto.py). O token em texto puro só
existe em memória, no momento de chamar a Graph API.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.models.account import InstagramAccount
from app.services import instagram_api

logger = logging.getLogger("inboxpilot.token")

# Renova quando faltar menos que isto para expirar.
REFRESH_MARGIN = timedelta(days=10)


def encrypt_token(plain: str) -> str:
    """Cifra um token para gravar no banco."""
    return crypto.encrypt(plain)


def read_token(account: InstagramAccount) -> str:
    """Decifra o token da conta (levanta crypto.TokenCryptoError se não der)."""
    return crypto.decrypt(account.access_token_enc)


def store_token(account: InstagramAccount, plain: str) -> None:
    """Grava (cifrado) um token novo na conta. Não faz commit."""
    account.access_token_enc = crypto.encrypt(plain)


async def get_valid_token(db: AsyncSession, account: InstagramAccount) -> str:
    """Devolve o token em texto puro, renovando antes se estiver perto de expirar.

    A renovação é best-effort: se falhar, segue com o token atual.
    """
    token = read_token(account)
    if account.token_expires_at is None:
        return token
    now = datetime.now(timezone.utc)
    if account.token_expires_at - now > REFRESH_MARGIN:
        return token
    try:
        data = await instagram_api.refresh_long_lived(token)
        token = data["access_token"]
        store_token(account, token)
        account.token_expires_at = now + timedelta(seconds=data.get("expires_in", 0))
        await db.commit()
        await db.refresh(account)
        logger.info("Token da conta %s renovado.", account.ig_user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao renovar token de %s: %s", account.ig_user_id, exc)
    return token
