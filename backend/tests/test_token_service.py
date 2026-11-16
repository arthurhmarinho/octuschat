"""Testes do token_service: cifra em repouso + renovação."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core import crypto
from app.models.account import InstagramAccount
from app.services import token_service

TOKEN = "IGAAtoken-original-1234567890"


class FakeDB:
    def __init__(self):
        self.commits = 0

    async def commit(self):
        self.commits += 1

    async def refresh(self, _obj):
        return None


def make_account(expires_in: timedelta | None) -> InstagramAccount:
    acc = InstagramAccount(ig_user_id="1")
    token_service.store_token(acc, TOKEN)
    acc.token_expires_at = (
        datetime.now(timezone.utc) + expires_in if expires_in is not None else None
    )
    return acc


def test_store_grava_cifrado_e_read_decifra(fernet_key):
    acc = make_account(None)
    assert acc.access_token_enc != TOKEN
    assert TOKEN not in acc.access_token_enc
    assert token_service.read_token(acc) == TOKEN


async def test_token_longe_de_expirar_nao_renova(fernet_key, monkeypatch):
    async def boom(_):
        raise AssertionError("não deveria renovar")

    monkeypatch.setattr(token_service.instagram_api, "refresh_long_lived", boom)
    db = FakeDB()
    acc = make_account(timedelta(days=30))
    assert await token_service.get_valid_token(db, acc) == TOKEN
    assert db.commits == 0


async def test_token_sem_expiracao_nao_renova(fernet_key):
    assert await token_service.get_valid_token(FakeDB(), make_account(None)) == TOKEN


async def test_token_perto_de_expirar_renova_e_grava_cifrado(fernet_key, monkeypatch):
    recebido = {}

    async def fake_refresh(token):
        recebido["token"] = token
        return {"access_token": "IGAAtoken-novo-0987654321", "expires_in": 5184000}

    monkeypatch.setattr(token_service.instagram_api, "refresh_long_lived", fake_refresh)
    db = FakeDB()
    acc = make_account(timedelta(days=2))

    novo = await token_service.get_valid_token(db, acc)

    assert recebido["token"] == TOKEN  # renovou usando o token decifrado
    assert novo == "IGAAtoken-novo-0987654321"
    assert "IGAAtoken-novo" not in acc.access_token_enc
    assert crypto.decrypt(acc.access_token_enc) == novo
    assert acc.token_expires_at > datetime.now(timezone.utc) + timedelta(days=59)
    assert db.commits == 1


async def test_falha_na_renovacao_segue_com_token_atual(fernet_key, monkeypatch):
    async def falha(_):
        raise RuntimeError("meta fora do ar")

    monkeypatch.setattr(token_service.instagram_api, "refresh_long_lived", falha)
    acc = make_account(timedelta(days=1))
    antes = acc.access_token_enc
    assert await token_service.get_valid_token(FakeDB(), acc) == TOKEN
    assert acc.access_token_enc == antes


def test_chave_errada_falha_alto(fernet_key, monkeypatch):
    from cryptography.fernet import Fernet

    from app.core.config import settings

    acc = make_account(None)
    monkeypatch.setattr(settings, "token_encryption_keys", Fernet.generate_key().decode())
    with pytest.raises(crypto.TokenCryptoError):
        token_service.read_token(acc)
