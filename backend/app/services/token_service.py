"""Gestão do ciclo de vida do token de longa duração da conta."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import InstagramAccount
from app.services import instagram_api

logger = logging.getLogger("inboxpilot.token")

# Renova quando faltar menos que isto para expirar.
REFRESH_MARGIN = timedelta(days=10)


async def ensure_fresh(db: AsyncSession, account: InstagramAccount) -> InstagramAccount:
    """Renova o token se estiver perto de expirar. Best-effort."""
    if account.token_expires_at is None:
        return account
    now = datetime.now(timezone.utc)
    if account.token_expires_at - now > REFRESH_MARGIN:
        return account
    try:
        data = await instagram_api.refresh_long_lived(account.access_token)
        account.access_token = data["access_token"]
        account.token_expires_at = now + timedelta(seconds=data.get("expires_in", 0))
        await db.commit()
        await db.refresh(account)
        logger.info("Token da conta %s renovado.", account.ig_user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao renovar token de %s: %s", account.ig_user_id, exc)
    return account
