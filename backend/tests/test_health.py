"""O ping externo usa /health: aceita GET e HEAD e não toca no banco."""

import httpx
import pytest
from httpx import ASGITransport

from app.core.database import engine, get_session
from app.main import app


@pytest.mark.parametrize("method", ["GET", "HEAD"])
async def test_health_aceita_get_e_head_sem_banco(method, monkeypatch):
    def proibido(*_a, **_kw):
        raise AssertionError("/health não pode usar o banco")

    async def sem_sessao():
        proibido()
        yield

    monkeypatch.setattr(type(engine), "connect", proibido)
    monkeypatch.setattr(type(engine), "begin", proibido)
    monkeypatch.setitem(app.dependency_overrides, get_session, sem_sessao)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.request(method, "/health")
    assert r.status_code == 200
    if method == "GET":
        assert r.json()["status"] == "ok"
