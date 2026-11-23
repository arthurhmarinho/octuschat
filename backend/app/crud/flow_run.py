"""Operações de banco para execuções de flow (`flow_runs`).

Cada escrita faz commit. O estado é a fonte da verdade do flow: grave-o ANTES
de enviar as ações do trecho seguinte (ver automation_engine).
"""

from datetime import timedelta

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.flow_run import (
    ACTIVE,
    FINISHED,
    RUNNING,
    WAIT_REPLY,
    WAITING,
    FlowRun,
)

_ACTIVE_WHERE = text("status IN ('running','waiting')")


async def get(db: AsyncSession, run_id: int) -> FlowRun | None:
    return await db.get(FlowRun, run_id)


async def create(
    db: AsyncSession,
    *,
    automation_id: int,
    account_id: str,
    contact_id: int,
    graph: dict,
    context: dict,
    trigger_ref: str | None = None,
    current_node_id: str | None = None,
) -> FlowRun | None:
    """Cria a execução. Devolve None se já existe uma ativa para o par.

    O índice único parcial é quem garante: dois webhooks simultâneos do mesmo
    contato não criam duas execuções.
    """
    stmt = (
        pg_insert(FlowRun)
        .values(
            automation_id=automation_id,
            account_id=account_id,
            contact_id=contact_id,
            graph=graph,
            context=context,
            trigger_ref=trigger_ref,
            current_node_id=current_node_id,
            status=RUNNING,
        )
        .on_conflict_do_nothing(
            index_elements=["automation_id", "contact_id"], index_where=_ACTIVE_WHERE
        )
        .returning(FlowRun.id)
    )
    run_id = (await db.execute(stmt)).scalar_one_or_none()
    await db.commit()
    if run_id is None:
        return None
    return await db.get(FlowRun, run_id)


async def find_waiting_reply(
    db: AsyncSession, account_id: str, contact_id: int
) -> FlowRun | None:
    """A execução mais recente que espera uma resposta deste contato."""
    result = await db.execute(
        select(FlowRun)
        .where(
            FlowRun.account_id == account_id,
            FlowRun.contact_id == contact_id,
            FlowRun.status == WAITING,
            FlowRun.waiting_for == WAIT_REPLY,
        )
        .order_by(FlowRun.created_at.desc(), FlowRun.id.desc())
        .limit(1)
    )
    return result.scalars().first()


async def claim_due(db: AsyncSession, limit: int) -> list[FlowRun]:
    """Reserva execuções esperando cujo `resume_at` já passou (SKIP LOCKED).

    Seguro com vários workers: cada execução vai para um só. As reservadas
    passam a `running` (continuam ativas); `waiting_for` fica como estava para
    o chamador saber se foi timeout de resposta ou fim de atraso.
    """
    ids = (
        select(FlowRun.id)
        .where(FlowRun.status == WAITING, FlowRun.resume_at <= func.now())
        .order_by(FlowRun.resume_at, FlowRun.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    stmt = (
        update(FlowRun)
        .where(FlowRun.id.in_(ids))
        .values(status=RUNNING)
        .returning(FlowRun)
        # populate_existing: se a sessão já conhece a linha, devolve o estado novo.
        .execution_options(synchronize_session=False, populate_existing=True)
    )
    runs = list((await db.execute(stmt)).scalars().all())
    await db.commit()
    return sorted(runs, key=lambda r: (r.resume_at, r.id))


async def save(db: AsyncSession, run: FlowRun, **fields) -> FlowRun:
    """Grava campos da execução (status, current_node_id, context, resume_at…)."""
    for name, value in fields.items():
        setattr(run, name, value)
    await db.commit()
    await db.refresh(run)
    return run


async def finish(
    db: AsyncSession, run: FlowRun, status: str, error: str | None = None
) -> FlowRun:
    """Encerra a execução (completed, expired, failed ou cancelled)."""
    assert status in FINISHED, status
    return await save(
        db,
        run,
        status=status,
        waiting_for=None,
        resume_at=None,
        last_error=error,
        finished_at=func.now(),
    )


async def cancel_active_for_contact(
    db: AsyncSession, account_id: str, contact_id: int
) -> int:
    """Cancela as execuções ativas do contato. Devolve quantas."""
    result = await db.execute(
        update(FlowRun)
        .where(
            FlowRun.account_id == account_id,
            FlowRun.contact_id == contact_id,
            FlowRun.status.in_(ACTIVE),
        )
        .values(status="cancelled", waiting_for=None, resume_at=None, finished_at=func.now())
    )
    await db.commit()
    return result.rowcount or 0


async def list_by_automation(
    db: AsyncSession, automation_id: int, limit: int = 50
) -> list[FlowRun]:
    result = await db.execute(
        select(FlowRun)
        .where(FlowRun.automation_id == automation_id)
        .order_by(FlowRun.created_at.desc(), FlowRun.id.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def requeue_stale(db: AsyncSession, older_than: timedelta) -> int:
    """Devolve a `waiting` (já vencidas) as execuções presas em `running`.

    Só as que estavam esperando (`waiting_for` preenchido): o worker as reservou
    e morreu antes de gravar o resultado. Elas voltam a ser reservadas.
    """
    result = await db.execute(
        update(FlowRun)
        .where(
            FlowRun.status == RUNNING,
            FlowRun.waiting_for.is_not(None),
            FlowRun.updated_at < func.now() - older_than,
        )
        .values(status=WAITING, resume_at=func.now())
    )
    await db.commit()
    return result.rowcount or 0


async def purge_finished(db: AsyncSession, older_than: timedelta) -> int:
    """Apaga execuções terminadas há mais de `older_than` (padrão do worker: 30 dias)."""
    result = await db.execute(
        delete(FlowRun).where(
            FlowRun.status.in_(FINISHED),
            FlowRun.finished_at < func.now() - older_than,
        )
    )
    await db.commit()
    return result.rowcount or 0
