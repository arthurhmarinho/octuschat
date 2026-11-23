"""Saúde do token (M.4): código 190 marca a conta; renovação limpa; janela proativa."""

from datetime import datetime, timedelta, timezone

import pytest

from app import crud
from app.models.account import InstagramAccount
from app.schemas.account import AccountRead
from app.services import instagram_api, token_service
from app.workers.webhook_worker import WebhookWorker
from tests.conftest import requires_pg

TOKEN = "IGAAtoken-original-1234567890"
NOW = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)


def err190():
    return instagram_api.InstagramAPIError("HTTP 400: token expirado (code 190)", 400, 190)


class FakeDB:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1

    async def refresh(self, _o):
        return None

    async def rollback(self):
        return None


def account(expires_in: timedelta | None, **kw) -> InstagramAccount:
    acc = InstagramAccount(ig_user_id="1", **kw)
    token_service.store_token(acc, TOKEN)
    acc.token_expires_at = datetime.now(timezone.utc) + expires_in if expires_in is not None else None
    return acc


# ── erro 190 ──────────────────────────────────────────────


def test_api_error_guarda_o_codigo_da_meta():
    import httpx
    resp = httpx.Response(400, json={"error": {"message": "Invalid OAuth access token", "code": 190}})
    with pytest.raises(instagram_api.InstagramAPIError) as exc:
        instagram_api._check(resp)  # noqa: SLF001
    assert exc.value.code == 190 and exc.value.status_code == 400


async def test_note_api_error_marca_so_no_190(fernet_key):
    db, acc = FakeDB(), account(None)
    assert await token_service.note_api_error(db, acc, RuntimeError("rede")) is False
    assert acc.token_invalid_at is None
    other = instagram_api.InstagramAPIError("HTTP 400: x (code 100)", 400, 100)
    assert await token_service.note_api_error(db, acc, other) is False
    assert await token_service.note_api_error(db, acc, err190()) is True
    assert acc.token_invalid_at is not None and db.commits == 1
    # segunda vez não regrava (mantém a data do primeiro erro)
    first = acc.token_invalid_at
    await token_service.note_api_error(db, acc, err190())
    assert acc.token_invalid_at == first and db.commits == 1


async def test_renovacao_sob_demanda_com_190_marca_a_conta(fernet_key, monkeypatch):
    async def falha(_):
        raise err190()

    monkeypatch.setattr(token_service.instagram_api, "refresh_long_lived", falha)
    acc = account(timedelta(days=1))
    assert await token_service.get_valid_token(FakeDB(), acc) == TOKEN
    assert acc.token_invalid_at is not None


async def test_renovacao_bem_sucedida_limpa_a_marca(fernet_key, monkeypatch):
    async def ok(_):
        return {"access_token": "IGAAnovo", "expires_in": 5184000}

    monkeypatch.setattr(token_service.instagram_api, "refresh_long_lived", ok)
    acc = account(timedelta(days=1), token_invalid_at=NOW)
    await token_service.get_valid_token(FakeDB(), acc)
    assert acc.token_invalid_at is None


# ── needs_reconnect ───────────────────────────────────────


def read(**kw):
    base = dict(ig_user_id="1", username="u", connected_at=NOW)
    return AccountRead(**{**base, **kw})


def test_needs_reconnect():
    assert read().needs_reconnect is False
    assert read(token_expires_at=datetime.now(timezone.utc) + timedelta(days=30)).needs_reconnect is False
    assert read(token_expires_at=datetime.now(timezone.utc) - timedelta(days=1)).needs_reconnect is True
    assert read(token_invalid_at=NOW).needs_reconnect is True


def test_needs_reconnect_sai_no_json_e_token_invalid_at_nao():
    data = read(token_invalid_at=NOW).model_dump(mode="json")
    assert data["needs_reconnect"] is True
    assert "token_invalid_at" not in data and "token_expires_at" in data


# ── renovação proativa (Postgres) ─────────────────────────


@pytest.fixture
async def accounts(pg_sessions, fernet_key):
    async with pg_sessions() as db:
        for ig, days, invalid in [
            ("perto", 5, None),        # entra na janela de 15 dias
            ("longe", 40, None),       # fora da janela
            ("recusada", 3, NOW),      # já recusada pela Meta: não tenta
            ("morta", 2, None),        # a Meta vai responder 190
            ("sem-data", None, None),  # sem expiração conhecida
        ]:
            acc = InstagramAccount(ig_user_id=ig, access_token_enc="x", token_invalid_at=invalid)
            token_service.store_token(acc, TOKEN)
            acc.token_expires_at = NOW + timedelta(days=days) if days is not None else None
            db.add(acc)
        await db.commit()
        yield db


@requires_pg
async def test_list_expiring_respeita_a_janela_e_a_marca(accounts):
    got = await crud.account.list_expiring(accounts, NOW + timedelta(days=15))
    assert sorted(a.ig_user_id for a in got) == ["morta", "perto"]


@requires_pg
async def test_refresh_expiring_renova_marca_e_ignora(accounts, monkeypatch):
    chamadas = []

    async def refresh(token):
        chamadas.append(token)
        if len(chamadas) == 1:
            return {"access_token": "IGAAnovo-1", "expires_in": 5184000}
        raise err190()

    monkeypatch.setattr(token_service.instagram_api, "refresh_long_lived", refresh)
    counts = await token_service.refresh_expiring(accounts, now=NOW)
    assert counts == {"renewed": 1, "invalidated": 1, "failed": 0}
    assert len(chamadas) == 2  # "longe", "recusada" e "sem-data" não foram tentadas

    for ig in ("perto", "morta", "longe", "recusada", "sem-data"):
        await accounts.refresh(await accounts.get(InstagramAccount, ig))
    por = {ig: await accounts.get(InstagramAccount, ig) for ig in ("perto", "morta", "longe", "recusada", "sem-data")}
    renovadas = [ig for ig in ("perto", "morta") if por[ig].token_expires_at > NOW + timedelta(days=50)]
    marcadas = [ig for ig in ("perto", "morta") if por[ig].token_invalid_at is not None]
    assert len(renovadas) == 1 and len(marcadas) == 1 and renovadas != marcadas
    # as que não entraram no sorteio ficam como estavam
    assert por["longe"].token_invalid_at is None and por["recusada"].token_invalid_at == NOW


@requires_pg
async def test_refresh_expiring_falha_comum_nao_marca(accounts, monkeypatch):
    async def refresh(_):
        raise RuntimeError("meta fora do ar")

    monkeypatch.setattr(token_service.instagram_api, "refresh_long_lived", refresh)
    counts = await token_service.refresh_expiring(accounts, now=NOW)
    assert counts == {"renewed": 0, "invalidated": 0, "failed": 2}
    got = await crud.account.list_expiring(accounts, NOW + timedelta(days=15))
    assert all(a.token_invalid_at is None for a in got)


@requires_pg
async def test_worker_renova_na_primeira_passagem_e_depois_a_cada_12h(pg_sessions, monkeypatch):
    chamadas = []

    async def renew(db):
        chamadas.append(1)
        return {"renewed": 0, "invalidated": 0, "failed": 0}

    monkeypatch.setattr(token_service, "refresh_expiring", renew)
    w = WebhookWorker(session_factory=pg_sessions)
    await w.maintenance(now=100.0)
    assert len(chamadas) == 1
    await w.maintenance(now=100.0 + 3600)
    assert len(chamadas) == 1
    await w.maintenance(now=100.0 + 12 * 3600 + 1)
    assert len(chamadas) == 2
