"""Ciclo de vida do token de acesso da conta (cifrado em repouso).

Único lugar que cifra/decifra o token: o banco guarda só
`access_token_enc` (Fernet, ver core/crypto.py). O token em texto puro só
existe em memória, no momento de chamar a Graph API.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app import crud

from app.core import crypto
from app.models.account import InstagramAccount
from app.services import instagram_api

logger = logging.getLogger("inboxpilot.token")

# Renova (sob demanda, ao usar o token) quando faltar menos que isto.
REFRESH_MARGIN = timedelta(days=10)
# Renovação proativa (worker): contas cujo token vence dentro desta janela.
PROACTIVE_WINDOW = timedelta(days=15)

# Código de erro da Meta para token inválido/expirado/revogado.
META_INVALID_TOKEN = 190


def is_invalid_token_error(exc: BaseException) -> bool:
    return isinstance(exc, instagram_api.InstagramAPIError) and exc.code == META_INVALID_TOKEN


async def mark_invalid(db: AsyncSession, account: InstagramAccount) -> None:
    """A Meta recusou o token: a UI passa a pedir "Reconectar"."""
    if account.token_invalid_at is None:
        account.token_invalid_at = datetime.now(timezone.utc)
        await db.commit()
        logger.warning("Token da conta %s recusado pela Meta (190).", account.ig_user_id)


async def note_api_error(
    db: AsyncSession, account: InstagramAccount, exc: BaseException
) -> bool:
    """Chame num `except` de qualquer chamada à Meta. Marca a conta se for 190."""
    if is_invalid_token_error(exc):
        await mark_invalid(db, account)
        return True
    return False


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
        account.token_invalid_at = None
        await db.commit()
        await db.refresh(account)
        logger.info("Token da conta %s renovado.", account.ig_user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao renovar token de %s: %s", account.ig_user_id, exc)
        await note_api_error(db, account, exc)
    return token


async def refresh_expiring(
    db: AsyncSession, now: datetime | None = None
) -> dict[str, int]:
    """Renova os tokens que vencem em breve (chamado pelo worker, ~a cada 12 h).

    Só contas com `token_invalid_at IS NULL`: uma conta já recusada pela Meta
    precisa de reconexão manual. Devolve contadores {renewed, invalidated, failed}.
    """
    now = now or datetime.now(timezone.utc)
    counts = {"renewed": 0, "invalidated": 0, "failed": 0}
    for account in await crud.account.list_expiring(db, now + PROACTIVE_WINDOW):
        try:
            data = await instagram_api.refresh_long_lived(read_token(account))
        except Exception as exc:  # noqa: BLE001
            # Nada foi alterado ainda: só classifica o erro.
            if await note_api_error(db, account, exc):
                counts["invalidated"] += 1
            else:
                counts["failed"] += 1
                logger.warning(
                    "Renovação proativa falhou para %s: %s", account.ig_user_id, exc
                )
            continue
        store_token(account, data["access_token"])
        account.token_expires_at = now + timedelta(seconds=data.get("expires_in", 0))
        account.token_invalid_at = None
        await db.commit()
        counts["renewed"] += 1
    return counts
