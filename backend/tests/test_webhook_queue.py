"""Testes da fila de webhooks contra um Postgres DE VERDADE.

SKIP LOCKED e ON CONFLICT não existem no SQLite, então estes testes só
rodam com TEST_DATABASE_URL definida (um banco descartável — o schema é
recriado a cada teste!). Ex.:

    TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5433/octus_test pytest
"""

import asyncio
import hashlib
import hmac
import json
import os
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app import crud
from app.core.config import settings
from app.core.database import Base, get_session
from app.models.webhook_event import DONE, FAILED, PENDING, PROCESSING, WebhookEvent
from app.workers import webhook_worker as worker_mod
from app.workers.webhook_worker import MAX_ATTEMPTS, WebhookWorker

TEST_DB = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL não definida")


@pytest.fixture
async def sessions():
    engine = create_async_engine(
        TEST_DB, poolclass=NullPool, connect_args={"prepare_threshold": None}
    )
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TYPE IF EXISTS trigger_type"))
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def ev(key: str, account="acc", kind="comment", payload=None):
    return {"dedupe_key": key, "account_id": account, "kind": kind, "payload": payload or {}}


async def all_events(sessions):
    async with sessions() as db:
        return (await db.execute(select(WebhookEvent).order_by(WebhookEvent.id))).scalars().all()


@pytest.fixture
def dispatch_calls(monkeypatch):
    """Substitui o engine: registra chamadas; falha se payload pedir."""
    calls = []

    async def fake_dispatch(db, kind, account_id, payload):
        calls.append((kind, account_id, payload))
        if payload.get("boom"):
            raise RuntimeError("falha simulada access_token=IGAAsegredo123")

    monkeypatch.setattr(worker_mod, "dispatch", fake_dispatch)
    return calls


# ── enqueue / dedupe ───────────────────────────────────────


async def test_enqueue_descarta_duplicados(sessions):
    async with sessions() as db:
        assert await crud.webhook_event.enqueue(db, [ev("a"), ev("b")]) == 2
        assert await crud.webhook_event.enqueue(db, [ev("a"), ev("c")]) == 1
        assert await crud.webhook_event.enqueue(db, []) == 0
    rows = await all_events(sessions)
    assert [r.dedupe_key for r in rows] == ["a", "b", "c"]
    assert all(r.status == PENDING and r.attempts == 0 for r in rows)


# ── claim com SKIP LOCKED ──────────────────────────────────


async def test_claims_concorrentes_nao_pegam_o_mesmo_evento(sessions):
    async with sessions() as db:
        await crud.webhook_event.enqueue(db, [ev(f"k{i}") for i in range(20)])

    async def claim():
        async with sessions() as db:
            return [e.id for e in await crud.webhook_event.claim_batch(db, 7)]

    results = await asyncio.gather(*(claim() for _ in range(5)))
    ids = [i for r in results for i in r]
    assert len(ids) == len(set(ids)) == 20  # todos pegos, nenhum repetido
    rows = await all_events(sessions)
    assert all(r.status == PROCESSING and r.attempts == 1 and r.locked_at for r in rows)


async def test_claim_respeita_available_at_e_ordem(sessions):
    async with sessions() as db:
        await crud.webhook_event.enqueue(db, [ev("1"), ev("2"), ev("3")])
        await db.execute(
            text("UPDATE webhook_events SET available_at = now() + interval '1 hour' WHERE dedupe_key='2'")
        )
        await db.commit()
        claimed = await crud.webhook_event.claim_batch(db, 10)
    assert [e.dedupe_key for e in claimed] == ["1", "3"]


# ── worker ─────────────────────────────────────────────────


async def test_worker_processa_e_marca_done(sessions, dispatch_calls):
    async with sessions() as db:
        await crud.webhook_event.enqueue(db, [ev("a", payload={"n": 1}), ev("b", kind="message")])
    w = WebhookWorker(session_factory=sessions)
    assert await w.run_once() == 2
    assert [c[0] for c in dispatch_calls] == ["comment", "message"]
    rows = await all_events(sessions)
    assert all(r.status == DONE and r.processed_at and r.locked_at is None for r in rows)
    assert await w.run_once() == 0  # nada mais pendente


async def test_falha_volta_para_fila_com_backoff_e_erro_limpo(sessions, dispatch_calls):
    async with sessions() as db:
        await crud.webhook_event.enqueue(db, [ev("x", payload={"boom": True})])
    w = WebhookWorker(session_factory=sessions)
    await w.run_once()
    [row] = await all_events(sessions)
    assert row.status == PENDING and row.attempts == 1
    assert "falha simulada" in row.last_error
    assert "IGAAsegredo123" not in row.last_error
    async with sessions() as db:
        futuro = (await db.execute(
            text("SELECT available_at > now() + interval '20 seconds' FROM webhook_events")
        )).scalar()
    assert futuro
    assert await w.run_once() == 0  # ainda no backoff


async def test_esgota_tentativas_e_vira_failed(sessions, dispatch_calls):
    async with sessions() as db:
        await crud.webhook_event.enqueue(db, [ev("x", payload={"boom": True})])
    w = WebhookWorker(session_factory=sessions)
    for _ in range(MAX_ATTEMPTS):
        async with sessions() as db:  # pula o backoff
            await db.execute(text("UPDATE webhook_events SET available_at = now()"))
            await db.commit()
        await w.run_once()
    [row] = await all_events(sessions)
    assert row.status == FAILED and row.attempts == MAX_ATTEMPTS
    assert len(dispatch_calls) == MAX_ATTEMPTS


async def test_limitador_adia_sem_contar_tentativa(sessions, dispatch_calls):
    class Limita:
        async def reserve(self, account_id):
            return 60.0

    async with sessions() as db:
        await crud.webhook_event.enqueue(db, [ev("x")])
    w = WebhookWorker(session_factory=sessions, limiter=Limita())
    await w.run_once()
    [row] = await all_events(sessions)
    assert row.status == PENDING and row.attempts == 0
    assert dispatch_calls == []


async def test_eventos_presos_voltam_para_fila(sessions):
    async with sessions() as db:
        await crud.webhook_event.enqueue(db, [ev("velho"), ev("novo")])
        await crud.webhook_event.claim_batch(db, 10)
        await db.execute(
            text("UPDATE webhook_events SET locked_at = now() - interval '10 minutes' WHERE dedupe_key='velho'")
        )
        await db.commit()
        assert await crud.webhook_event.requeue_stale(db, timedelta(minutes=5)) == 1
    status = {r.dedupe_key: r.status for r in await all_events(sessions)}
    assert status == {"velho": PENDING, "novo": PROCESSING}


async def test_purge_remove_so_done_antigos(sessions):
    async with sessions() as db:
        await crud.webhook_event.enqueue(db, [ev("velho"), ev("recente"), ev("falhou")])
        await db.execute(text(
            "UPDATE webhook_events SET status='done', processed_at = now() - interval '30 days' WHERE dedupe_key='velho';"
            "UPDATE webhook_events SET status='done', processed_at = now() WHERE dedupe_key='recente';"
            "UPDATE webhook_events SET status='failed', processed_at = now() - interval '30 days' WHERE dedupe_key='falhou';"
        ))
        await db.commit()
        assert await crud.webhook_event.purge_done(db, timedelta(days=14)) == 1
    assert sorted(r.dedupe_key for r in await all_events(sessions)) == ["falhou", "recente"]


async def test_loop_acorda_com_notify(sessions, dispatch_calls):
    w = WebhookWorker(session_factory=sessions, poll_interval=30)
    task = asyncio.create_task(w.run())
    await asyncio.sleep(0.3)  # worker ocioso, esperando até 30s
    async with sessions() as db:
        await crud.webhook_event.enqueue(db, [ev("a")])
    w.notify()
    for _ in range(50):
        if dispatch_calls:
            break
        await asyncio.sleep(0.05)
    await w.stop()
    await asyncio.wait_for(task, timeout=5)
    assert len(dispatch_calls) == 1  # processou bem antes dos 30s


# ── endpoint ───────────────────────────────────────────────


@pytest.fixture
async def client(sessions, monkeypatch):
    from app.main import app

    async def override():
        async with sessions() as db:
            yield db

    notified = []
    monkeypatch.setattr(worker_mod.worker, "notify", lambda: notified.append(1))
    monkeypatch.setattr(settings, "meta_app_secret", "segredo-app")
    app.dependency_overrides[get_session] = override
    transport = httpx.ASGITransport(app=app)  # não roda o lifespan (sem worker)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        c.notified = notified
        yield c
    app.dependency_overrides.clear()


def signed(body: dict) -> tuple[bytes, dict]:
    raw = json.dumps(body).encode()
    sig = "sha256=" + hmac.new(b"segredo-app", raw, hashlib.sha256).hexdigest()
    return raw, {"X-Hub-Signature-256": sig, "Content-Type": "application/json"}


BODY = {
    "object": "instagram",
    "entry": [
        {
            "id": "acc",
            "changes": [{"field": "comments", "value": {"id": "c1", "text": "quero"}}],
            "messaging": [{"sender": {"id": "u"}, "message": {"mid": "m1", "text": "oi"}}],
        }
    ],
}


async def test_endpoint_enfileira_e_responde_200(client, sessions):
    raw, headers = signed(BODY)
    resp = await client.post("/webhooks/instagram", content=raw, headers=headers)
    assert resp.status_code == 200 and resp.json() == {"status": "ok"}
    assert [r.dedupe_key for r in await all_events(sessions)] == ["comment:c1", "mid:m1"]
    assert client.notified == [1]

    # Reenvio da Meta: 200 de novo, nada duplicado, worker não é acordado.
    resp = await client.post("/webhooks/instagram", content=raw, headers=headers)
    assert resp.status_code == 200
    assert len(await all_events(sessions)) == 2
    assert client.notified == [1]


async def test_endpoint_rejeita_assinatura_invalida(client, sessions):
    raw, headers = signed(BODY)
    headers["X-Hub-Signature-256"] = "sha256=" + "0" * 64
    resp = await client.post("/webhooks/instagram", content=raw, headers=headers)
    assert resp.status_code == 403
    assert await all_events(sessions) == []


async def test_endpoint_rejeita_corpo_que_nao_e_json(client):
    raw = b"isto nao e json"
    sig = "sha256=" + hmac.new(b"segredo-app", raw, hashlib.sha256).hexdigest()
    resp = await client.post(
        "/webhooks/instagram", content=raw, headers={"X-Hub-Signature-256": sig}
    )
    assert resp.status_code == 400
