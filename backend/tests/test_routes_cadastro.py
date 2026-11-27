"""Cadastro por convite, redefinição e onboarding (precisa de TEST_DATABASE_URL)."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import func, select

from app import crud
from app.core.config import settings
from app.core.database import get_session
from app.main import app
from app.models.user import User
from tests.conftest import requires_pg

pytestmark = requires_pg

SECRET = "segredo-de-teste"
PASSWORD = "senha-bem-comprida"


def hdr(user_id: int | None = None) -> dict:
    h = {"X-Octus-Secret": SECRET}
    if user_id is not None:
        h["X-Octus-User"] = str(user_id)
    return h


@pytest.fixture
async def world(pg_sessions, monkeypatch):
    """Um admin e um usuário comum (criado pelo script: sem convite)."""
    monkeypatch.setattr(settings, "api_secret", SECRET)
    monkeypatch.setattr(settings, "meta_app_id", "1234567890")

    async def override():
        async with pg_sessions() as s:
            yield s

    app.dependency_overrides[get_session] = override
    async with pg_sessions() as db:
        admin = await crud.user.create(db, "dono@x.com", "Dono", PASSWORD, is_admin=True,
                                       must_change_password=False)
        other = await crud.user.create(db, "comum@x.com", "Comum", PASSWORD,
                                       must_change_password=False)
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield {"c": c, "sessions": pg_sessions, "admin": admin, "other": other}
    app.dependency_overrides.clear()


async def invite(world, ig="fulano.ig", name="Fulano", email=None) -> dict:
    async with world["sessions"]() as db:
        row, token = await crud.invite.create(db, "signup", name=name, email=email, ig_username=ig)
    return {"invite": {"id": row.id}, "token": token}


def form(token, **kw) -> dict:
    return {"token": token, "name": "Fulano", "email": "fulano@x.com", "password": PASSWORD, **kw}


async def register(world, token, **kw):
    return await world["c"].post("/auth/register", headers=hdr(), json=form(token, **kw))


async def info(world, token) -> dict:
    r = await world["c"].get(f"/auth/invites/{token}", headers=hdr())
    assert r.status_code == 200
    return r.json()


async def count_users(world) -> int:
    async with world["sessions"]() as db:
        return (await db.execute(select(func.count()).select_from(User))).scalar_one()


async def expire(world, invite_id):
    async with world["sessions"]() as db:
        row = await crud.invite.get(db, invite_id)
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        await db.commit()


INVALID = {"valid": False, "purpose": None, "name": None, "email": None, "ig_username": None}


# ── C.1: cadastro ─────────────────────────────────────────


async def test_cadastro_feliz(world):
    created = await invite(world, email="Fulano@X.com")
    token = created["token"]
    assert await info(world, token) == {
        "valid": True, "purpose": "signup", "name": "Fulano",
        "email": "fulano@x.com", "ig_username": "fulano.ig",
    }
    r = await register(world, token, email="  FULANO@x.com ", name=" Fulano da Silva ")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "fulano@x.com" and body["name"] == "Fulano da Silva"
    assert body["is_admin"] is False and body["must_change_password"] is False
    assert "password" not in r.text.replace("must_change_password", "")
    async with world["sessions"]() as db:
        row = await crud.invite.get(db, created["invite"]["id"])
        assert row.used_at is not None and row.user_id == body["id"]
    login = await world["c"].post("/auth/login", headers=hdr(),
                                  json={"email": "fulano@x.com", "password": PASSWORD})
    assert login.status_code == 200


@pytest.mark.parametrize("how", ["vencido", "usado", "cancelado", "inexistente"])
async def test_convite_que_nao_vale(world, how):
    created = await invite(world)
    token, invite_id = created["token"], created["invite"]["id"]
    if how == "vencido":
        await expire(world, invite_id)
    elif how == "usado":
        assert (await register(world, token, email="primeiro@x.com")).status_code == 200
    elif how == "cancelado":
        async with world["sessions"]() as db:
            assert await crud.invite.revoke(db, invite_id)
    else:
        token = "nao-existe"
    before = await count_users(world)
    assert await info(world, token) == INVALID
    r = await register(world, token)
    assert r.status_code == 410 and r.json() == {"detail": "Este convite não vale mais"}
    # sem convite válido, a rota não conta quem tem conta
    r = await register(world, token, email="dono@x.com")
    assert r.status_code == 410
    assert await count_users(world) == before


async def test_email_repetido_nao_consome_o_convite(world):
    token = (await invite(world))["token"]
    r = await register(world, token, email="COMUM@x.com")
    assert r.status_code == 409
    assert r.json()["detail"] == "Já existe uma conta com este e-mail. Entre com ela"
    assert (await info(world, token))["valid"] is True
    assert (await register(world, token)).status_code == 200


async def test_corrida_de_email_vira_409_e_devolve_o_convite(world, monkeypatch):
    """O e-mail aparece entre a conferência e o INSERT: o índice único decide."""
    token = (await invite(world))["token"]

    async def ninguem(_db, _email):
        return None

    monkeypatch.setattr(crud.user, "get_by_email", ninguem)
    r = await register(world, token, email="comum@x.com")
    assert r.status_code == 409
    monkeypatch.undo()
    monkeypatch.setattr(settings, "api_secret", SECRET)
    assert (await info(world, token))["valid"] is True


@pytest.mark.parametrize("bad", [
    {"password": "curta"}, {"name": "   "}, {"email": "sem-arroba"},
])
async def test_dado_invalido_nao_consome_o_convite(world, bad):
    token = (await invite(world))["token"]
    r = await register(world, token, **bad)
    assert r.status_code == 422 and isinstance(r.json()["detail"], str)
    assert (await info(world, token))["valid"] is True


@pytest.mark.parametrize("method,path,body", [
    ("get", "/auth/invites/abc", None),
    ("post", "/auth/register", form("abc")),
    ("post", "/auth/reset", {"token": "abc", "password": PASSWORD}),
])
async def test_rotas_publicas_exigem_o_segredo_da_api(world, method, path, body):
    r = await world["c"].request(method, path, json=body)
    assert r.status_code == 401


# ── C.1: redefinição ──────────────────────────────────────


async def reset_token(world, user_id) -> str:
    async with world["sessions"]() as db:
        _, token = await crud.invite.create(db, "reset", user_id=user_id)
    return token


async def do_reset(world, token, password="outra-senha-comprida"):
    return await world["c"].post("/auth/reset", headers=hdr(),
                                 json={"token": token, "password": password})


async def test_reset_troca_a_senha_uma_vez(world):
    other = world["other"]
    token = await reset_token(world, other.id)
    got = await info(world, token)
    assert got["purpose"] == "reset" and got["email"] == "comum@x.com" and got["name"] == "Comum"
    weak = await do_reset(world, token, "curta")
    assert weak.status_code == 422 and (await info(world, token))["valid"] is True
    r = await do_reset(world, token)
    assert r.status_code == 200 and r.json()["id"] == other.id
    assert r.json()["must_change_password"] is False
    assert (await do_reset(world, token)).status_code == 410
    for password, expected in ((PASSWORD, 401), ("outra-senha-comprida", 200)):
        login = await world["c"].post("/auth/login", headers=hdr(),
                                      json={"email": "comum@x.com", "password": password})
        assert login.status_code == expected


async def test_um_tipo_de_convite_nao_serve_para_o_outro(world):
    signup = (await invite(world))["token"]
    reset = await reset_token(world, world["other"].id)
    assert (await do_reset(world, signup)).status_code == 410
    assert (await register(world, reset)).status_code == 410
    # nenhum dos dois foi gasto
    assert (await info(world, signup))["valid"] is True
    assert (await info(world, reset))["valid"] is True


# ── C.1: onboarding ───────────────────────────────────────


async def test_onboarding_mostra_so_os_dados_do_proprio_usuario(world):
    created = await invite(world)
    uid = (await register(world, created["token"])).json()["id"]
    await invite(world, ig="outra", name="Outra")
    async with world["sessions"]() as db:
        await crud.account.upsert(db, "c1", "enc", username="do_comum",
                                  owner_user_id=world["other"].id)
    r = await world["c"].get("/auth/onboarding", headers=hdr(uid))
    assert r.json() == {"invited_ig_username": "fulano.ig", "meta_tester_added": False,
                        "accounts": []}
    async with world["sessions"]() as db:
        await crud.invite.mark_meta_added(db, created["invite"]["id"])
        await crud.account.upsert(db, "f1", "enc", username="fulano.ig", owner_user_id=uid)
    body = (await world["c"].get("/auth/onboarding", headers=hdr(uid))).json()
    assert body["meta_tester_added"] is True
    assert [a["ig_user_id"] for a in body["accounts"]] == ["f1"]
    assert "enc" not in str(body)
    # quem não veio de convite não herda o de ninguém
    body = (await world["c"].get("/auth/onboarding", headers=hdr(world["other"].id))).json()
    assert body["invited_ig_username"] is None and body["meta_tester_added"] is False
    assert [a["ig_user_id"] for a in body["accounts"]] == ["c1"]
    assert (await world["c"].get("/auth/onboarding", headers=hdr())).status_code == 401
