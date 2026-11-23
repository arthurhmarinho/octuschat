"""Testes da autenticação da API (Parte A): segredo do proxy e state do OAuth."""

import time

import pytest
from fastapi import HTTPException

from app.core import auth
from app.core.config import settings


@pytest.fixture(autouse=True)
def api_secret(monkeypatch):
    monkeypatch.setattr(settings, "api_secret", "segredo-de-teste")


async def test_segredo_correto_passa():
    assert await auth.require_api_secret("segredo-de-teste") is None


@pytest.mark.parametrize("enviado", [None, "", "errado", "segredo-de-teste "])
async def test_segredo_ausente_ou_errado_da_401(enviado):
    with pytest.raises(HTTPException) as exc:
        await auth.require_api_secret(enviado)
    assert exc.value.status_code == 401


async def test_sem_api_secret_configurado_recusa_tudo(monkeypatch):
    monkeypatch.setattr(settings, "api_secret", "")
    with pytest.raises(HTTPException):
        await auth.require_api_secret("")


def test_state_valido_devolve_o_uid():
    assert auth.verify_oauth_state(auth.make_oauth_state(42)) == 42


def test_state_expirado():
    old = time.time() - auth.OAUTH_STATE_TTL - 1
    assert auth.verify_oauth_state(auth.make_oauth_state(1, now=old)) is None


def test_state_do_futuro_e_rejeitado():
    assert auth.verify_oauth_state(auth.make_oauth_state(1, now=time.time() + 600)) is None


def test_state_adulterado_no_timestamp():
    ts, nonce, uid, sig = auth.make_oauth_state(1).split(".")
    assert auth.verify_oauth_state(f"{int(ts) + 1}.{nonce}.{uid}.{sig}") is None


def test_state_com_uid_trocado_e_rejeitado():
    """Trocar o uid (ex.: 1 -> 2) sem refazer a assinatura não passa."""
    ts, nonce, uid, sig = auth.make_oauth_state(1).split(".")
    assert auth.verify_oauth_state(f"{ts}.{nonce}.2.{sig}") is None


def test_state_formato_antigo_de_3_partes_e_recusado():
    ts, nonce = str(int(time.time())), "abc"
    legacy_sig = auth._state_sig(f"{ts}.{nonce}")
    assert auth.verify_oauth_state(f"{ts}.{nonce}.{legacy_sig}") is None


def test_state_assinado_com_outro_segredo(monkeypatch):
    state = auth.make_oauth_state(1)
    monkeypatch.setattr(settings, "api_secret", "outro")
    assert auth.verify_oauth_state(state) is None


def test_state_sem_segredo_configurado_recusa(monkeypatch):
    state = auth.make_oauth_state(1)
    monkeypatch.setattr(settings, "api_secret", "")
    assert auth.verify_oauth_state(state) is None


@pytest.mark.parametrize("state", ["", "abc", "a.b", "a.b.c", "a.b.c.d.e", "x.y.z.w"])
def test_state_mal_formado(state):
    assert auth.verify_oauth_state(state) is None


# ── current_user ──────────────────────────────────────────


class FakeDB:
    def __init__(self, users):
        self.users = users

    async def get(self, model, pk):
        return self.users.get(pk)


async def test_current_user_ok():
    sentinel = object()
    got = await auth.current_user(FakeDB({7: sentinel}), "segredo-de-teste", "7")
    assert got is sentinel


@pytest.mark.parametrize("secret,uid", [
    (None, "7"),            # sem segredo
    ("errado", "7"),        # segredo errado
    ("segredo-de-teste", None),   # sem usuário
    ("segredo-de-teste", ""),
    ("segredo-de-teste", "abc"),
    ("segredo-de-teste", "-1"),
    ("segredo-de-teste", "7.5"),
    ("segredo-de-teste", "٣"),    # dígito não-ASCII
    ("segredo-de-teste", "99"),   # usuário inexistente
])
async def test_current_user_recusa(secret, uid):
    with pytest.raises(HTTPException) as exc:
        await auth.current_user(FakeDB({7: object()}), secret, uid)
    assert exc.value.status_code == 401
