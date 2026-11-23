"""Hash de senha com scrypt da stdlib (sem dependência nova).

Formato guardado: ``scrypt$<N>$<r>$<p>$<salt_b64>$<hash_b64>``. Os parâmetros
vão junto, então dá para aumentar o custo depois sem invalidar quem já tem senha.
"""

import base64
import hashlib
import hmac
import secrets

MIN_PASSWORD_LEN = 10

_N = 16384
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16


class WeakPassword(ValueError):
    """Senha abaixo do mínimo."""


def check_policy(password: str) -> None:
    if len(password) < MIN_PASSWORD_LEN:
        raise WeakPassword(f"A senha precisa ter pelo menos {MIN_PASSWORD_LEN} caracteres")


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _derive(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    # maxmem acima do padrão (32 MB) para tolerar custos maiores no futuro.
    return hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=dklen,
        maxmem=128 * n * r * 2 + 1024 * 1024,
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = _derive(password, salt, _N, _R, _P, _DKLEN)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """Compara em tempo constante. Formato inválido = False (nunca levanta)."""
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(hash_b64, validate=True)
        actual = _derive(password, salt, int(n), int(r), int(p), len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)
