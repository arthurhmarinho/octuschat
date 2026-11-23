"""flow_runs: criação, unicidade da execução ativa, reserva por vencimento, limpeza."""

import asyncio
from datetime import timedelta

import pytest
from sqlalchemy import text

from app import crud
from app.models.automation import Automation, TriggerType
from app.models.flow_run import COMPLETED, RUNNING, WAIT_REPLY, WAIT_TIMER, WAITING
from app.schemas.automation import AutomationCreate
from app.workers.webhook_worker import WebhookWorker
from tests.conftest import requires_pg

pytestmark = requires_pg

G = {"version": 3, "start": "n1", "edges": [], "nodes": [{"id": "n1", "type": "message", "text": "Oi"}]}


@pytest.fixture
async def db(pg_sessions):
    async with pg_sessions() as s:
        u = await crud.user.create(s, "a@x.com", "A", "senha-bem-longa")
        await crud.account.upsert(s, "acc", "enc", owner_user_id=u.id)
        s.auto = await crud.automation.create(
            s, AutomationCreate(name="a", trigger="dm_any", graph=G, account_id="acc"))
        s.auto2 = await crud.automation.create(
            s, AutomationCreate(name="b", trigger="dm_any", graph=G, account_id="acc"))
        s.c1 = await crud.contact.upsert(s, "acc", "u1", username="um")
        s.c2 = await crud.contact.upsert(s, "acc", "u2", username="dois")
        yield s


async def gone(db, run_id) -> bool:
    """A linha sumiu do banco? (`db.get` olharia só o cache da sessão.)"""
    n = (await db.execute(text("select count(*) from flow_runs where id=:i"), {"i": run_id})).scalar_one()
    return n == 0


async def mk(db, contact=None, auto=None, **kw):
    return await crud.flow_run.create(
        db, automation_id=(auto or db.auto).id, account_id="acc",
        contact_id=(contact or db.c1).id, graph=G, context={"text": "oi", "vars": {}}, **kw)


async def test_create_grava_copia_do_grafo_e_estado_inicial(db):
    run = await mk(db, trigger_ref="mid:1", current_node_id="n1")
    assert run.status == RUNNING and run.graph == G and run.trigger_ref == "mid:1"
    assert run.context == {"text": "oi", "vars": {}} and run.finished_at is None


async def test_uma_execucao_ativa_por_automacao_e_contato(db):
    first = await mk(db)
    assert first is not None
    assert await mk(db) is None                        # mesma automação e contato
    assert await mk(db, contact=db.c2) is not None     # outro contato
    assert await mk(db, auto=db.auto2) is not None     # outra automação
    await crud.flow_run.save(db, first, status=WAITING, waiting_for=WAIT_REPLY)
    assert await mk(db) is None                        # waiting também é ativa
    await crud.flow_run.finish(db, first, COMPLETED)
    assert await mk(db) is not None                    # terminada libera o par


async def test_criacao_simultanea_cria_so_uma(pg_sessions, db):
    async def one():
        async with pg_sessions() as s:
            return await crud.flow_run.create(
                s, automation_id=db.auto.id, account_id="acc", contact_id=db.c1.id,
                graph=G, context={})
    results = await asyncio.gather(*[one() for _ in range(6)])
    assert sum(r is not None for r in results) == 1


async def test_find_waiting_reply_pega_a_mais_recente_e_ignora_timer(db):
    old = await mk(db, auto=db.auto)
    await crud.flow_run.save(db, old, status=WAITING, waiting_for=WAIT_REPLY)
    new = await mk(db, auto=db.auto2)
    await crud.flow_run.save(db, new, status=WAITING, waiting_for=WAIT_REPLY)
    assert (await crud.flow_run.find_waiting_reply(db, "acc", db.c1.id)).id == new.id
    await crud.flow_run.save(db, new, waiting_for=WAIT_TIMER)
    assert (await crud.flow_run.find_waiting_reply(db, "acc", db.c1.id)).id == old.id
    assert await crud.flow_run.find_waiting_reply(db, "acc", db.c2.id) is None
    assert await crud.flow_run.find_waiting_reply(db, "outra", db.c1.id) is None


async def test_claim_due_so_pega_vencidas_e_nao_repete(db):
    due = await mk(db, contact=db.c1)
    later = await mk(db, contact=db.c2)
    await db.execute(text("update flow_runs set status='waiting', waiting_for='timer', resume_at=now() - interval '1 minute' where id=:i"), {"i": due.id})
    await db.execute(text("update flow_runs set status='waiting', waiting_for='reply', resume_at=now() + interval '1 hour' where id=:i"), {"i": later.id})
    await db.commit()
    got = await crud.flow_run.claim_due(db, 10)
    assert [r.id for r in got] == [due.id]
    assert got[0].status == RUNNING and got[0].waiting_for == WAIT_TIMER  # sabe o que esperava
    assert await crud.flow_run.claim_due(db, 10) == []                    # já reservada


async def test_claim_due_com_dois_workers_nao_duplica(pg_sessions, db):
    ids = []
    for i in range(6):
        c = await crud.contact.upsert(db, "acc", f"x{i}")
        r = await mk(db, contact=c)
        ids.append(r.id)
    await db.execute(text("update flow_runs set status='waiting', waiting_for='timer', resume_at=now() - interval '1 minute'"))
    await db.commit()

    async def worker():
        async with pg_sessions() as s:
            return [r.id for r in await crud.flow_run.claim_due(s, 3)]
    a, b = await asyncio.gather(worker(), worker())
    assert not set(a) & set(b) and set(a) | set(b) <= set(ids)
    assert len(a) + len(b) == 6


async def test_finish_limpa_espera_e_registra_erro(db):
    run = await mk(db)
    await crud.flow_run.save(db, run, status=WAITING, waiting_for=WAIT_REPLY)
    done = await crud.flow_run.finish(db, run, "expired", "outside_window")
    assert done.status == "expired" and done.last_error == "outside_window"
    assert done.waiting_for is None and done.resume_at is None and done.finished_at is not None


async def test_cancel_active_for_contact(db):
    a = await mk(db, auto=db.auto)
    b = await mk(db, auto=db.auto2)
    other = await mk(db, contact=db.c2)
    assert await crud.flow_run.cancel_active_for_contact(db, "acc", db.c1.id) == 2
    for r in (a, b):
        await db.refresh(r)
        assert r.status == "cancelled" and r.finished_at is not None
    await db.refresh(other)
    assert other.status == RUNNING


async def test_list_by_automation_ordem_e_limite(db):
    runs = []
    for i in range(4):
        c = await crud.contact.upsert(db, "acc", f"l{i}")
        runs.append(await mk(db, contact=c))
    await mk(db, auto=db.auto2)
    got = await crud.flow_run.list_by_automation(db, db.auto.id, limit=3)
    assert [r.id for r in got] == [r.id for r in reversed(runs)][:3]


async def test_excluir_a_automacao_apaga_as_execucoes(db):
    run = await mk(db)
    await db.delete(await db.get(Automation, db.auto.id))
    await db.commit()
    assert await gone(db, run.id)


async def test_requeue_stale_so_devolve_as_que_esperavam(db):
    stuck = await mk(db, contact=db.c1)
    fresh_no_wait = await mk(db, contact=db.c2)
    await db.execute(text("update flow_runs set status='running', waiting_for='timer', updated_at=now() - interval '10 minutes' where id=:i"), {"i": stuck.id})
    await db.execute(text("update flow_runs set updated_at=now() - interval '10 minutes' where id=:i"), {"i": fresh_no_wait.id})
    await db.commit()
    assert await crud.flow_run.requeue_stale(db, timedelta(minutes=5)) == 1
    await db.refresh(stuck)
    assert stuck.status == WAITING
    # e agora ela pode ser reservada de novo
    assert [r.id for r in await crud.flow_run.claim_due(db, 5)] == [stuck.id]


async def test_purge_finished_so_apaga_terminadas_antigas(db):
    old = await mk(db, contact=db.c1)
    recent = await mk(db, contact=db.c2)
    active = await mk(db, auto=db.auto2)
    await crud.flow_run.finish(db, old, COMPLETED)
    await crud.flow_run.finish(db, recent, COMPLETED)
    await db.execute(text("update flow_runs set finished_at=now() - interval '31 days' where id=:i"), {"i": old.id})
    await db.commit()
    assert await crud.flow_run.purge_finished(db, timedelta(days=30)) == 1
    assert await gone(db, old.id)
    assert not await gone(db, recent.id)
    assert not await gone(db, active.id)


async def test_manutencao_do_worker_limpa_execucoes_antigas(pg_sessions, db):
    run = await mk(db)
    await crud.flow_run.finish(db, run, COMPLETED)
    await db.execute(text("update flow_runs set finished_at=now() - interval '40 days'"))
    await db.commit()
    w = WebhookWorker(session_factory=pg_sessions)
    w._last_renew = 0.0  # evita a renovação de tokens neste teste
    await w.maintenance(now=10**6)
    assert await gone(db, run.id)
