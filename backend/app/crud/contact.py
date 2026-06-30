"""Operações de banco para contatos."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact


async def upsert(
    db: AsyncSession,
    account_id: str,
    ig_user_id: str,
    username: str | None = None,
    touch: bool = True,
) -> Contact:
    """Cria o contato se não existir; opcionalmente atualiza last_message_at."""
    result = await db.execute(
        select(Contact).where(
            Contact.account_id == account_id, Contact.ig_user_id == ig_user_id
        )
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        contact = Contact(account_id=account_id, ig_user_id=ig_user_id, username=username)
        db.add(contact)
    if username and not contact.username:
        contact.username = username
    if touch:
        contact.last_message_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(contact)
    return contact


async def get(db: AsyncSession, contact_id: int) -> Contact | None:
    return await db.get(Contact, contact_id)


async def list_by_account(db: AsyncSession, account_id: str) -> list[Contact]:
    result = await db.execute(
        select(Contact)
        .where(Contact.account_id == account_id)
        .order_by(Contact.last_message_at.desc().nullslast())
    )
    return list(result.scalars().all())
