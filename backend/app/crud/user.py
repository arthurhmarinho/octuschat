"""Operações de banco para usuários."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.passwords import check_policy, hash_password
from app.models.user import User


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == normalize_email(email)))
    return result.scalars().first()


async def create(
    db: AsyncSession,
    email: str,
    name: str,
    password: str,
    *,
    is_admin: bool = False,
    must_change_password: bool = True,
) -> User:
    """Cria o usuário. `password` em texto: o hash é feito aqui."""
    check_policy(password)
    user = User(
        email=normalize_email(email),
        name=name.strip(),
        password_hash=hash_password(password),
        is_admin=is_admin,
        must_change_password=must_change_password,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def set_password(
    db: AsyncSession, user: User, password: str, *, must_change: bool = False
) -> User:
    check_policy(password)
    user.password_hash = hash_password(password)
    user.must_change_password = must_change
    await db.commit()
    await db.refresh(user)
    return user


async def touch_login(db: AsyncSession, user: User) -> None:
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
