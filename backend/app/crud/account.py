"""Operações de banco para contas do Instagram."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import InstagramAccount


async def upsert(
    db: AsyncSession,
    ig_user_id: str,
    access_token: str,
    username: str | None = None,
    token_expires_at: datetime | None = None,
    ig_id: str | None = None,
) -> InstagramAccount:
    """Cria ou atualiza a conta (re-conexão atualiza o token)."""
    account = await db.get(InstagramAccount, ig_user_id)
    if account is None:
        account = InstagramAccount(ig_user_id=ig_user_id, access_token=access_token)
        db.add(account)
    else:
        account.access_token = access_token
    if username is not None:
        account.username = username
    if token_expires_at is not None:
        account.token_expires_at = token_expires_at
    if ig_id is not None:
        account.ig_id = ig_id
    await db.commit()
    await db.refresh(account)
    return account


async def get(db: AsyncSession, ig_user_id: str) -> InstagramAccount | None:
    return await db.get(InstagramAccount, ig_user_id)


async def get_by_any_id(db: AsyncSession, some_id: str) -> InstagramAccount | None:
    """Busca a conta pelo ig_user_id OU pelo ig_id (id do webhook)."""
    result = await db.execute(
        select(InstagramAccount).where(
            (InstagramAccount.ig_user_id == some_id)
            | (InstagramAccount.ig_id == some_id)
        )
    )
    return result.scalars().first()


async def list_all(db: AsyncSession) -> list[InstagramAccount]:
    result = await db.execute(select(InstagramAccount))
    return list(result.scalars().all())
