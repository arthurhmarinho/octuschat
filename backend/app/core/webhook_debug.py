"""Buffer em memória dos últimos webhooks recebidos (para diagnóstico).

Registra TODA requisição que chega em /webhooks/instagram, antes da checagem
de assinatura, para respondermos: a Meta está entregando? a assinatura confere?
Reseta quando o processo reinicia (Render free dorme) — use durante um teste ativo.
"""

from collections import deque
from datetime import datetime, timezone

_hits: deque[dict] = deque(maxlen=25)


def record(sig_present: bool, sig_valid: bool | None, body: bytes) -> None:
    _hits.append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "sig_present": sig_present,
            "sig_valid": sig_valid,
            "len": len(body),
            "snippet": body[:400].decode("utf-8", "replace"),
        }
    )


def recent() -> list[dict]:
    return list(reversed(_hits))
