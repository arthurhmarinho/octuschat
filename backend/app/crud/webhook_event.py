"""Fila de eventos do webhook (tabela webhook_events) — operações de banco.

Todas as escritas fazem commit: cada passo da fila é sua própria transação.
"""

from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook_event import DONE, FAILED, PENDING, PROCESSING, WebhookEvent


async def enqueue(db: AsyncSession, events: list[dict]) -> int:
    """Grava os eventos, ignorando duplicados (dedupe_key). Devolve quantos entraram."""
    if not events:
        return 0
    stmt = (
        pg_insert(WebhookEvent)
        .values(events)
        .on_conflict_do_nothing(index_elements=["dedupe_key"])
        .returning(WebhookEvent.id)
    )
    inserted = (await db.execute(stmt)).scalars().all()
    await db.commit()
    return len(inserted)


async def claim_batch(db: AsyncSession, limit: int) -> list[WebhookEvent]:
    """Reserva até `limit` eventos pendentes e já liberados (SKIP LOCKED).

    Seguro com vários workers/instâncias: cada linha vai para um só.
    Marca como `processing`, carimba `locked_at` e conta a tentativa.
    """
    ids = (
        select(WebhookEvent.id)
        .where(WebhookEvent.status == PENDING, WebhookEvent.available_at <= func.now())
        .order_by(WebhookEvent.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    stmt = (
        update(WebhookEvent)
        .where(WebhookEvent.id.in_(ids))
        .values(
            status=PROCESSING,
            locked_at=func.now(),
            attempts=WebhookEvent.attempts + 1,
        )
        .returning(WebhookEvent)
        .execution_options(synchronize_session=False)
    )
    events = list((await db.execute(stmt)).scalars().all())
    await db.commit()
    return sorted(events, key=lambda e: e.id)


async def mark_done(db: AsyncSession, event_id: int) -> None:
    await db.execute(
        update(WebhookEvent)
        .where(WebhookEvent.id == event_id)
        .values(status=DONE, processed_at=func.now(), locked_at=None, last_error=None)
    )
    await db.commit()


async def mark_retry(
    db: AsyncSession, event_id: int, delay: timedelta, error: str | None
) -> None:
    """Devolve à fila para tentar de novo após `delay`."""
    await db.execute(
        update(WebhookEvent)
        .where(WebhookEvent.id == event_id)
        .values(
            status=PENDING,
            locked_at=None,
            available_at=func.now() + delay,
            last_error=error,
        )
    )
    await db.commit()


async def mark_failed(db: AsyncSession, event_id: int, error: str) -> None:
    await db.execute(
        update(WebhookEvent)
        .where(WebhookEvent.id == event_id)
        .values(status=FAILED, locked_at=None, processed_at=func.now(), last_error=error)
    )
    await db.commit()


async def defer(db: AsyncSession, event_id: int, delay: timedelta) -> None:
    """Adia sem contar tentativa (ex.: rate limit da conta)."""
    await db.execute(
        update(WebhookEvent)
        .where(WebhookEvent.id == event_id)
        .values(
            status=PENDING,
            locked_at=None,
            available_at=func.now() + delay,
            attempts=WebhookEvent.attempts - 1,
        )
    )
    await db.commit()


async def requeue_stale(db: AsyncSession, older_than: timedelta) -> int:
    """Devolve à fila eventos presos em `processing` (worker morreu no meio)."""
    result = await db.execute(
        update(WebhookEvent)
        .where(
            WebhookEvent.status == PROCESSING,
            WebhookEvent.locked_at < func.now() - older_than,
        )
        .values(status=PENDING, locked_at=None)
    )
    await db.commit()
    return result.rowcount or 0


async def purge_done(db: AsyncSession, older_than: timedelta) -> int:
    """Apaga eventos já processados há mais de `older_than` (economiza espaço)."""
    result = await db.execute(
        delete(WebhookEvent).where(
            WebhookEvent.status == DONE,
            WebhookEvent.processed_at < func.now() - older_than,
        )
    )
    await db.commit()
    return result.rowcount or 0
