"""Operações de banco para mensagens."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message


async def create(
    db: AsyncSession,
    account_id: str,
    contact_id: int,
    direction: str,
    text: str,
    source: str,
) -> Message:
    msg = Message(
        account_id=account_id,
        contact_id=contact_id,
        direction=direction,
        text=text,
        source=source,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def list_by_contact(db: AsyncSession, contact_id: int) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.contact_id == contact_id)
        .order_by(Message.created_at.asc())
    )
    return list(result.scalars().all())
