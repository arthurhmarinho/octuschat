"""`config_problems` é puro: cada regra e o caso válido."""

import logging

import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings, settings as app_settings
from app.core.config_check import config_problems

KEY = Fernet.generate_key().decode()
VALID = {
    "environment": "production",
    "meta_app_id": "1234567890123456",
    "meta_app_secret": "um-segredo-da-meta",
    "oauth_redirect_uri": "https://api.exemplo.com/instagram/callback",
    "webhook_verify_token": "um-token-proprio",
    "token_encryption_keys": KEY,
    "api_secret": "um-segredo-da-api",
}


def make(**kw) -> Settings:
    return Settings(_env_file=None, **{**VALID, **kw})


def test_configuracao_valida_nao_tem_problema():
    assert config_problems(make()) == []


def test_http_vale_fora_de_producao():
    s = make(environment="development", oauth_redirect_uri="http://localhost:8000/instagram/callback")
    assert config_problems(s) == []


@pytest.mark.parametrize("change,name", [
    ({"meta_app_id": ""}, "META_APP_ID"),
    ({"meta_app_id": "abc"}, "META_APP_ID"),
    ({"meta_app_id": "1234"}, "META_APP_ID"),
    ({"meta_app_id": "1" * 21}, "META_APP_ID"),
    ({"meta_app_id": "123456789 "}, "META_APP_ID"),
    ({"meta_app_id": "123456789\n"}, "META_APP_ID"),
    ({"meta_app_secret": ""}, "META_APP_SECRET"),
    ({"oauth_redirect_uri": "http://api.exemplo.com/instagram/callback"}, "OAUTH_REDIRECT_URI"),
    ({"oauth_redirect_uri": "https://api.exemplo.com/callback"}, "OAUTH_REDIRECT_URI"),
    ({"webhook_verify_token": "troque-este-valor"}, "WEBHOOK_VERIFY_TOKEN"),
    ({"token_encryption_keys": ""}, "TOKEN_ENCRYPTION_KEYS"),
    ({"token_encryption_keys": "nao-e-fernet"}, "TOKEN_ENCRYPTION_KEYS"),
    ({"api_secret": ""}, "API_SECRET"),
])
def test_cada_regra(change, name):
    [problem] = config_problems(make(**change))
    assert problem.startswith(name)


def test_as_mensagens_nunca_trazem_o_valor():
    bad = {
        "meta_app_id": "valor-do-app-id",
        "oauth_redirect_uri": "http://host-secreto.exemplo/x",
        "token_encryption_keys": "chave-quebrada-secreta",
    }
    text = " ".join(config_problems(make(**bad)))
    assert not any(value in text for value in bad.values()) and "host-secreto" not in text


async def test_boot_loga_cada_problema_e_nao_derruba(monkeypatch, caplog):
    from app.main import app, lifespan

    for name, value in {**VALID, "meta_app_id": "abc", "api_secret": ""}.items():
        monkeypatch.setattr(app_settings, name, value)
    monkeypatch.setattr(app_settings, "webhook_worker_enabled", False)
    with caplog.at_level(logging.ERROR, logger="inboxpilot"):
        async with lifespan(app):
            pass
    messages = [r.getMessage() for r in caplog.records]
    assert len(messages) == 2
    assert any("META_APP_ID" in m for m in messages) and any("API_SECRET" in m for m in messages)
