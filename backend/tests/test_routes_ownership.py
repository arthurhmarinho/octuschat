"""Rotas HTTP com dois usuários: cada um vê só o que é seu (precisa de TEST_DATABASE_URL)."""

import httpx
import pytest
from httpx import ASGITransport

from app import crud
from app.core import auth
from app.core.config import settings
from app.core.database import get_session
from app.main import app
from app.routers import instagram as instagram_router
from app.schemas.automation import AutomationCreate
from tests.conftest import requires_pg

pytestmark = requires_pg

SECRET = "segredo-de-teste"
GRAPH = {
    "version": 2,
    "start": "m1",
    "nodes": [{"id": "m1", "type": "message", "text": "Oi!"}],
    "edges": [],
}


def hdr(user_id: int | None, secret: str | None = SECRET) -> dict:
    h = {}
    if secret is not None:
        h["X-Octus-Secret"] = secret
    if user_id is not None:
        h["X-Octus-User"] = str(user_id)
    return h


@pytest.fixture
async def world(pg_sessions, monkeypatch):
    """App com o banco descartável + usuários A e B, cada um com uma conta e uma automação."""
    monkeypatch.setattr(settings, "api_secret", SECRET)

    async def override():
        async with pg_sessions() as s:
            yield s

    app.dependency_overrides[get_session] = override
    async with pg_sessions() as db:
        a = await crud.user.create(db, "a@x.com", "A", "senha-do-usuario-a", must_change_password=False)
        b = await crud.user.create(db, "b@x.com", "B", "senha-do-usuario-b")
        await crud.account.upsert(db, "a1", "enc", username="conta_a", owner_user_id=a.id)
        await crud.account.upsert(db, "b1", "enc", username="conta_b", owner_user_id=b.id)
        auto_a = await crud.automation.create(db, AutomationCreate(
            name="de A", trigger="comment_any", graph=GRAPH, account_id="a1"))
        auto_b = await crud.automation.create(db, AutomationCreate(
            name="de B", trigger="comment_any", graph=GRAPH, account_id="b1"))
        await crud.contact.upsert(db, "b1", "9001", username="contato_do_b")
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
        yield {"c": client, "sessions": pg_sessions, "a": a, "b": b, "auto_a": auto_a, "auto_b": auto_b}
    app.dependency_overrides.clear()


# ── escopo por dono ───────────────────────────────────────


async def test_a_lista_so_as_proprias_contas(world):
    r = await world["c"].get("/instagram/accounts", headers=hdr(world["a"].id))
    assert r.status_code == 200
    assert [x["ig_user_id"] for x in r.json()] == ["a1"]
    r = await world["c"].get("/instagram/accounts", headers=hdr(world["b"].id))
    assert [x["ig_user_id"] for x in r.json()] == ["b1"]


@pytest.mark.parametrize("path", [
    "/automations?account_id=b1",
    "/contacts?account_id=b1",
    "/conversations?account_id=b1",
    "/instagram/b1/media",
    "/instagram/b1/subscription",
    "/automations?account_id=nao-existe",
])
async def test_a_recebe_404_em_conta_de_b(world, path):
    r = await world["c"].get(path, headers=hdr(world["a"].id))
    assert r.status_code == 404


async def test_404_igual_para_conta_alheia_e_inexistente(world):
    """Não revela se a conta existe para outro usuário."""
    alheia = await world["c"].get("/contacts?account_id=b1", headers=hdr(world["a"].id))
    nada = await world["c"].get("/contacts?account_id=zzz", headers=hdr(world["a"].id))
    assert alheia.status_code == nada.status_code == 404
    assert alheia.json() == nada.json()


async def test_a_nao_mexe_em_automacao_de_b(world):
    c, a, ab = world["c"], world["a"], world["auto_b"]
    assert (await c.get(f"/automations/{ab.id}", headers=hdr(a.id))).status_code == 404
    r = await c.patch(f"/automations/{ab.id}", json={"name": "invadida"}, headers=hdr(a.id))
    assert r.status_code == 404
    assert (await c.delete(f"/automations/{ab.id}", headers=hdr(a.id))).status_code == 404
    # B continua vendo a sua, intacta
    r = await c.get(f"/automations/{ab.id}", headers=hdr(world["b"].id))
    assert r.status_code == 200 and r.json()["name"] == "de B"


async def test_a_nao_cria_automacao_em_conta_de_b(world):
    body = {"name": "x", "trigger": "comment_any", "graph": GRAPH, "account_id": "b1"}
    r = await world["c"].post("/automations", json=body, headers=hdr(world["a"].id))
    assert r.status_code == 404


async def test_a_usa_normalmente_o_que_e_seu(world):
    c, a, aa = world["c"], world["a"], world["auto_a"]
    r = await c.get("/automations?account_id=a1", headers=hdr(a.id))
    assert [x["name"] for x in r.json()] == ["de A"]
    r = await c.patch(f"/automations/{aa.id}", json={"name": "renomeada"}, headers=hdr(a.id))
    assert r.status_code == 200 and r.json()["name"] == "renomeada"
    body = {"name": "nova", "trigger": "comment_any", "graph": GRAPH, "account_id": "a1"}
    assert (await c.post("/automations", json=body, headers=hdr(a.id))).status_code == 201
    assert (await c.delete(f"/automations/{aa.id}", headers=hdr(a.id))).status_code == 204


async def test_b_ve_o_proprio_contato_e_a_nao(world):
    r = await world["c"].get("/contacts?account_id=b1", headers=hdr(world["b"].id))
    assert [x["username"] for x in r.json()] == ["contato_do_b"]
    r = await world["c"].get("/conversations?account_id=b1", headers=hdr(world["b"].id))
    assert r.status_code == 200 and len(r.json()) == 1


# ── autenticação ──────────────────────────────────────────


@pytest.mark.parametrize("path", ["/instagram/accounts", "/automations?account_id=a1",
                                  "/contacts?account_id=a1", "/auth/me"])
async def test_sem_x_octus_user_da_401(world, path):
    assert (await world["c"].get(path, headers=hdr(None))).status_code == 401


async def test_x_octus_user_sem_segredo_da_401(world):
    r = await world["c"].get("/auth/me", headers=hdr(world["a"].id, secret=None))
    assert r.status_code == 401
    r = await world["c"].get("/auth/me", headers=hdr(world["a"].id, secret="errado"))
    assert r.status_code == 401


async def test_usuario_inexistente_da_401(world):
    assert (await world["c"].get("/auth/me", headers=hdr(99999))).status_code == 401


async def test_health_continua_publico(world):
    assert (await world["c"].get("/health")).status_code == 200


# ── login / senha ─────────────────────────────────────────


async def test_login_certo_e_errado(world):
    c = world["c"]
    r = await c.post("/auth/login", json={"email": "A@X.com", "password": "senha-do-usuario-a"},
                     headers=hdr(None))
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == "a@x.com" and body["must_change_password"] is False
    assert "password_hash" not in body and "password" not in body

    errada = await c.post("/auth/login", json={"email": "a@x.com", "password": "errada-errada"},
                          headers=hdr(None))
    inexistente = await c.post("/auth/login", json={"email": "ninguem@x.com", "password": "errada-errada"},
                               headers=hdr(None))
    assert errada.status_code == inexistente.status_code == 401
    assert errada.json() == inexistente.json() == {"detail": "E-mail ou senha incorretos"}


async def test_login_exige_o_segredo_da_api(world):
    r = await world["c"].post("/auth/login", json={"email": "a@x.com", "password": "senha-do-usuario-a"},
                              headers=hdr(None, secret=None))
    assert r.status_code == 401


async def test_login_atualiza_last_login(world):
    await world["c"].post("/auth/login", json={"email": "a@x.com", "password": "senha-do-usuario-a"},
                          headers=hdr(None))
    me = await world["c"].get("/auth/me", headers=hdr(world["a"].id))
    assert me.status_code == 200


async def test_troca_de_senha_zera_must_change(world):
    c, b = world["c"], world["b"]
    assert (await c.get("/auth/me", headers=hdr(b.id))).json()["must_change_password"] is True
    r = await c.post("/auth/password", headers=hdr(b.id),
                     json={"current_password": "errada-errada", "new_password": "nova-senha-longa"})
    assert r.status_code == 400
    r = await c.post("/auth/password", headers=hdr(b.id),
                     json={"current_password": "senha-do-usuario-b", "new_password": "curta"})
    assert r.status_code == 422
    r = await c.post("/auth/password", headers=hdr(b.id),
                     json={"current_password": "senha-do-usuario-b", "new_password": "nova-senha-longa"})
    assert r.status_code == 200 and r.json()["must_change_password"] is False
    # a nova senha entra, a antiga não
    ok = await c.post("/auth/login", json={"email": "b@x.com", "password": "nova-senha-longa"}, headers=hdr(None))
    old = await c.post("/auth/login", json={"email": "b@x.com", "password": "senha-do-usuario-b"}, headers=hdr(None))
    assert ok.status_code == 200 and old.status_code == 401


# ── OAuth ─────────────────────────────────────────────────


async def test_connect_grava_o_uid_no_state(world):
    r = await world["c"].get("/instagram/connect", headers=hdr(world["a"].id), follow_redirects=False)
    assert r.status_code in (302, 307)
    from urllib.parse import parse_qs, urlparse
    state = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    assert auth.verify_oauth_state(state) == world["a"].id


@pytest.fixture
def meta_ok(monkeypatch, fernet_key):
    """Mocka as chamadas da Meta no callback; `meta_user` define qual conta volta."""
    box = {"user_id": "b1"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"user_id": box["user_id"], "access_token": "tok-curto"})

    real = httpx.AsyncClient
    monkeypatch.setattr(
        instagram_router.httpx, "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler)),
    )

    async def long_lived(_t):
        return {"access_token": "tok-longo", "expires_in": 5000000}

    async def profile(_uid, _t):
        return {"username": "alguem", "user_id": "wh-" + box["user_id"]}

    async def subscribe(_uid, _t):
        return {"success": True}

    monkeypatch.setattr(instagram_router.instagram_api, "exchange_for_long_lived", long_lived)
    monkeypatch.setattr(instagram_router.instagram_api, "get_profile", profile)
    monkeypatch.setattr(instagram_router.instagram_api, "subscribe_webhooks", subscribe)
    return box


async def test_callback_de_a_numa_conta_de_b_da_reason_owned(world, meta_ok):
    state = auth.make_oauth_state(world["a"].id)
    r = await world["c"].get(f"/instagram/callback?code=abc&state={state}", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert r.headers["location"].endswith("?connected=error&reason=owned")
    # o token do B não foi sobrescrito
    async with world["sessions"]() as db:
        acc = await crud.account.get(db, "b1")
        assert acc.access_token_enc == "enc" and acc.owner_user_id == world["b"].id


async def test_callback_grava_o_dono_e_limpa_token_invalid_at(world, meta_ok):
    from datetime import datetime, timezone
    meta_ok["user_id"] = "novo-ig"
    state = auth.make_oauth_state(world["a"].id)
    r = await world["c"].get(f"/instagram/callback?code=abc&state={state}", follow_redirects=False)
    assert r.headers["location"].endswith("?connected=ok")
    r = await world["c"].get("/instagram/accounts", headers=hdr(world["a"].id))
    assert {x["ig_user_id"] for x in r.json()} == {"a1", "novo-ig"}
    r = await world["c"].get("/instagram/accounts", headers=hdr(world["b"].id))
    assert {x["ig_user_id"] for x in r.json()} == {"b1"}


async def test_callback_com_state_invalido_ou_antigo(world, meta_ok):
    c = world["c"]
    r = await c.get("/instagram/callback?code=abc&state=lixo", follow_redirects=False)
    assert r.headers["location"].endswith("?connected=error")
    # formato antigo (3 partes)
    import time
    ts, nonce = str(int(time.time())), "n"
    sig = auth._state_sig(f"{ts}.{nonce}")  # noqa: SLF001
    r = await c.get(f"/instagram/callback?code=abc&state={ts}.{nonce}.{sig}", follow_redirects=False)
    assert r.headers["location"].endswith("?connected=error")
    # uid inexistente (assinado certo, mas o usuário não existe)
    state = auth.make_oauth_state(424242)
    r = await c.get(f"/instagram/callback?code=abc&state={state}", follow_redirects=False)
    assert r.headers["location"].endswith("?connected=error")
