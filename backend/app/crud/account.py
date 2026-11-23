"""Operações de banco para contas do Instagram."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import InstagramAccount


class AccountOwnedByOther(Exception):
    """A conta do Instagram já está ligada a outro usuário do painel."""


async def upsert(
    db: AsyncSession,
    ig_user_id: str,
    access_token_enc: str,
    username: str | None = None,
    token_expires_at: datetime | None = None,
    ig_id: str | None = None,
    owner_user_id: int | None = None,
) -> InstagramAccount:
    """Cria ou atualiza a conta (re-conexão atualiza o token).

    `access_token_enc` já vem cifrado (token_service.encrypt_token).
    `owner_user_id`: grava o dono só se a conta ainda não tiver um; se já for de
    OUTRO usuário, levanta `AccountOwnedByOther` sem alterar nada.
    """
    account = await db.get(InstagramAccount, ig_user_id)
    if account is None:
        account = InstagramAccount(
            ig_user_id=ig_user_id,
            access_token_enc=access_token_enc,
            owner_user_id=owner_user_id,
        )
        db.add(account)
    else:
        if owner_user_id is not None:
            if account.owner_user_id is None:
                account.owner_user_id = owner_user_id
            elif account.owner_user_id != owner_user_id:
                raise AccountOwnedByOther(ig_user_id)
        account.access_token_enc = access_token_enc
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


async def list_by_owner(db: AsyncSession, user_id: int) -> list[InstagramAccount]:
    result = await db.execute(
        select(InstagramAccount)
        .where(InstagramAccount.owner_user_id == user_id)
        .order_by(InstagramAccount.connected_at)
    )
    return list(result.scalars().all())


async def get_owned(
    db: AsyncSession, user_id: int, ig_user_id: str
) -> InstagramAccount | None:
    """A conta só se for deste usuário; senão None (o chamador responde 404)."""
    account = await db.get(InstagramAccount, ig_user_id)
    if account is None or account.owner_user_id != user_id:
        return None
    return account
