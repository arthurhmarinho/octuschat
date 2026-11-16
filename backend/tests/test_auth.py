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


def test_state_valido():
    assert auth.verify_oauth_state(auth.make_oauth_state())


def test_state_expirado():
    old = time.time() - auth.OAUTH_STATE_TTL - 1
    assert not auth.verify_oauth_state(auth.make_oauth_state(now=old))


def test_state_do_futuro_e_rejeitado():
    assert not auth.verify_oauth_state(auth.make_oauth_state(now=time.time() + 600))


def test_state_adulterado():
    ts, nonce, sig = auth.make_oauth_state().split(".")
    assert not auth.verify_oauth_state(f"{int(ts) + 1}.{nonce}.{sig}")


def test_state_assinado_com_outro_segredo(monkeypatch):
    state = auth.make_oauth_state()
    monkeypatch.setattr(settings, "api_secret", "outro")
    assert not auth.verify_oauth_state(state)


@pytest.mark.parametrize("state", ["", "abc", "a.b", "a.b.c.d", "x.y.z"])
def test_state_mal_formado(state):
    assert not auth.verify_oauth_state(state)
