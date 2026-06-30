"""Verificação de assinatura dos webhooks da Meta (X-Hub-Signature-256)."""

import hashlib
import hmac


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
