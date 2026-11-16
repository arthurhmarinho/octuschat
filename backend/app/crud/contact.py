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
    profile_pic: str | None = None,
    touch: bool = True,
    inbound: bool = False,
) -> Contact:
    """Cria o contato se não existir; atualiza username/foto/last_message_at.

    `inbound=True` (mensagem recebida por DM) também atualiza
    `last_inbound_at`, base da janela de 24h.
    """
    result = await db.execute(
        select(Contact).where(
            Contact.account_id == account_id, Contact.ig_user_id == ig_user_id
        )
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        contact = Contact(account_id=account_id, ig_user_id=ig_user_id, username=username)
        db.add(contact)
    if username:
        contact.username = username
    if profile_pic:
        contact.profile_pic = profile_pic
    now = datetime.now(timezone.utc)
    if touch:
        contact.last_message_at = now
    if inbound:
        contact.last_inbound_at = now
    await db.commit()
    await db.refresh(contact)
    return contact


async def exists(db: AsyncSession, account_id: str, ig_user_id: str) -> bool:
    """True se o contato já existe. Usado para saber se é a 1ª interação
    (condição `is_new_contact` do flow) — chamar ANTES do upsert."""
    result = await db.execute(
        select(Contact.id).where(
            Contact.account_id == account_id, Contact.ig_user_id == ig_user_id
        )
    )
    return result.scalar_one_or_none() is not None


async def find(db: AsyncSession, account_id: str, ig_user_id: str) -> Contact | None:
    """Contato pelo IGSID, sem criar."""
    result = await db.execute(
        select(Contact).where(
            Contact.account_id == account_id, Contact.ig_user_id == ig_user_id
        )
    )
    return result.scalar_one_or_none()


async def get(db: AsyncSession, contact_id: int) -> Contact | None:
    return await db.get(Contact, contact_id)


async def list_by_account(db: AsyncSession, account_id: str) -> list[Contact]:
    result = await db.execute(
        select(Contact)
        .where(Contact.account_id == account_id)
        .order_by(Contact.last_message_at.desc().nullslast())
    )
    return list(result.scalars().all())
