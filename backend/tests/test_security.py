"""Testes de verify_meta_signature (X-Hub-Signature-256 dos webhooks da Meta)."""

import hashlib
import hmac

import pytest

from app.core.security import verify_meta_signature

SECRET = "app-secret-de-teste"
BODY = b'{"object":"instagram","entry":[{"id":"123"}]}'


def sign(body: bytes, secret: str = SECRET) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_assinatura_valida():
    assert verify_meta_signature(BODY, sign(BODY), SECRET)


def test_corpo_vazio_com_assinatura_valida():
    assert verify_meta_signature(b"", sign(b""), SECRET)


def test_corpo_alterado_e_rejeitado():
    assert not verify_meta_signature(BODY + b" ", sign(BODY), SECRET)


def test_secret_errado_e_rejeitado():
    assert not verify_meta_signature(BODY, sign(BODY, "outro-secret"), SECRET)


@pytest.mark.parametrize("header", [None, "", "sha256=", "sha1=abc", "abc123"])
def test_header_ausente_ou_mal_formado(header):
    assert not verify_meta_signature(BODY, header, SECRET)


def test_sem_prefixo_sha256_e_rejeitado_mesmo_com_hash_certo():
    digest = sign(BODY).split("=", 1)[1]
    assert not verify_meta_signature(BODY, digest, SECRET)


def test_hexdigest_em_maiusculas_e_rejeitado():
    # A Meta envia em minúsculas; comparação é exata.
    assert not verify_meta_signature(BODY, sign(BODY).upper().replace("SHA256=", "sha256="), SECRET)


def test_assinatura_truncada_e_rejeitada():
    assert not verify_meta_signature(BODY, sign(BODY)[:-2], SECRET)


def test_corpo_com_unicode():
    body = '{"text":"quero o preço 🚀"}'.encode()
    assert verify_meta_signature(body, sign(body), SECRET)


# ── redact_secrets ──────────────────────────────────────────

from app.core.security import redact_secrets  # noqa: E402


@pytest.mark.parametrize(
    ("texto", "segredo"),
    [
        ("GET https://graph.instagram.com/v21.0/me?fields=id&access_token=IGAAxyz123", "IGAAxyz123"),
        ("url?client_secret=abc123&grant_type=x", "abc123"),
        ("callback?code=AQDcodigo123#_", "AQDcodigo123"),
        ("Authorization: Bearer IGAAtokenqualquer.abc-def_123", "IGAAtokenqualquer"),
        ("token solto IGAAJ1234567890abcdefghijklmnop no meio", "IGAAJ1234567890abcdefghijklmnop"),
        ("token EAAB1234567890abcdefghijklmnop facebook", "EAAB1234567890abcdefghijklmnop"),
    ],
)
def test_redact_remove_segredos(texto, segredo):
    limpo = redact_secrets(texto)
    assert segredo not in limpo
    assert "***" in limpo


def test_redact_preserva_texto_comum():
    texto = "HTTP 400: Invalid OAuth access token (code 190)"
    assert redact_secrets(texto) == texto
