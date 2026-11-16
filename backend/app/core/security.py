"""Segurança: assinatura dos webhooks da Meta e remoção de segredos de textos."""

import hashlib
import hmac
import re


def verify_meta_signature(
    payload: bytes, signature_header: str | None, app_secret: str
) -> bool:
    """Valida o header `X-Hub-Signature-256` (HMAC-SHA256 do corpo cru).

    A Meta envia `sha256=<hexdigest>`. Comparamos em tempo constante com o
    HMAC calculado usando o App Secret.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    received = signature_header.split("=", 1)[1]
    expected = hmac.new(
        app_secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received)


# Padrões de segredo que não podem ir para logs, banco ou respostas da API.
_SECRET_PATTERNS = [
    re.compile(r"(access_token|client_secret|code)=[^&\s'\"]+", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+", re.IGNORECASE),
    # Tokens da Meta: IGAA… (Instagram Login) e EAA… (Facebook Login).
    re.compile(r"\b(IGAA|IGQV|EAA)[A-Za-z0-9_\-]{20,}"),
]


def redact_secrets(text: str) -> str:
    """Remove tokens/segredos de uma string (mensagens de erro, URLs)."""
    text = _SECRET_PATTERNS[0].sub(r"\1=***", text)
    text = _SECRET_PATTERNS[1].sub(r"\1***", text)
    return _SECRET_PATTERNS[2].sub("***", text)
