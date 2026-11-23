"""Escopo por dono: toda rota com `account_id` passa por aqui."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.account import InstagramAccount
from app.models.user import User

NOT_FOUND = "Conta do Instagram não conectada"


async def owned_account(account_id: str, user: User, db: AsyncSession) -> InstagramAccount:
    """A conta do usuário ou 404.

    404 (e não 403) para não revelar que a conta existe para outro usuário.
    """
    account = await crud.account.get_owned(db, user.id, account_id)
    if account is None:
        raise HTTPException(404, NOT_FOUND)
    return account
