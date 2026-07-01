"""Operações de banco para o log de mensagens (idempotência/auditoria)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message_log import MessageLog


async def exists_for_comment(db: AsyncSession, comment_id: str) -> bool:
    result = await db.execute(
        select(MessageLog.id).where(MessageLog.comment_id == comment_id)
    )
    return result.first() is not None


async def recent(db: AsyncSession, limit: int = 10) -> list[MessageLog]:
    result = await db.execute(
        select(MessageLog).order_by(MessageLog.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
