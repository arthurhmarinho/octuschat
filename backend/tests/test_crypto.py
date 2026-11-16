"""Testes da criptografia dos tokens (core/crypto.py)."""

import pytest
from cryptography.fernet import Fernet

from app.core import crypto
from app.core.config import settings

TOKEN = "IGAAexemplo-de-token-da-meta-1234567890"


def test_ida_e_volta(fernet_key):
    enc = crypto.encrypt(TOKEN)
    assert enc != TOKEN
    assert TOKEN not in enc
    assert crypto.decrypt(enc) == TOKEN


def test_cada_cifragem_e_diferente(fernet_key):
    assert crypto.encrypt(TOKEN) != crypto.encrypt(TOKEN)


def test_sem_chave_falha(monkeypatch):
    monkeypatch.setattr(settings, "token_encryption_keys", "")
    assert not crypto.is_configured()
    with pytest.raises(crypto.TokenCryptoError, match="não configurada"):
        crypto.encrypt(TOKEN)


def test_chave_invalida_falha(monkeypatch):
    monkeypatch.setattr(settings, "token_encryption_keys", "nao-e-uma-chave-fernet")
    assert not crypto.is_configured()
    with pytest.raises(crypto.TokenCryptoError, match="inválida"):
        crypto.encrypt(TOKEN)


def test_chave_errada_nao_decifra(fernet_key, monkeypatch):
    enc = crypto.encrypt(TOKEN)
    monkeypatch.setattr(settings, "token_encryption_keys", Fernet.generate_key().decode())
    with pytest.raises(crypto.TokenCryptoError):
        crypto.decrypt(enc)


def test_texto_puro_nao_decifra(fernet_key):
    with pytest.raises(crypto.TokenCryptoError):
        crypto.decrypt(TOKEN)


def test_rotacao_de_chave(fernet_key, monkeypatch):
    antiga = fernet_key
    enc_antigo = crypto.encrypt(TOKEN)

    nova = Fernet.generate_key().decode()
    # Fase 1: nova na frente, antiga ainda aceita (com espaços, tolerados).
    monkeypatch.setattr(settings, "token_encryption_keys", f"{nova} , {antiga}")
    assert crypto.decrypt(enc_antigo) == TOKEN
    enc_novo = crypto.rotate(enc_antigo)

    # Fase 2: só a nova — o token rotacionado continua legível; o antigo não.
    monkeypatch.setattr(settings, "token_encryption_keys", nova)
    assert crypto.decrypt(enc_novo) == TOKEN
    with pytest.raises(crypto.TokenCryptoError):
        crypto.decrypt(enc_antigo)
