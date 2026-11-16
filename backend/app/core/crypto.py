"""Criptografia simétrica (Fernet) dos tokens de acesso da Meta.

`TOKEN_ENCRYPTION_KEYS` aceita várias chaves separadas por vírgula
(MultiFernet): a primeira cifra, todas decifram. Para rotacionar, coloque a
chave nova na frente, rode `python -m scripts.rotate_token_key` e depois
remova a antiga.

Não use direto fora de `token_service` — é lá que o token é decifrado, e só
no momento de usar.
"""

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings


class TokenCryptoError(RuntimeError):
    """Chave ausente/inválida ou token que não decifra com as chaves atuais."""


def _keys() -> list[str]:
    return [k.strip() for k in settings.token_encryption_keys.split(",") if k.strip()]


def _fernet() -> MultiFernet:
    keys = _keys()
    if not keys:
        raise TokenCryptoError("TOKEN_ENCRYPTION_KEYS não configurada.")
    try:
        return MultiFernet([Fernet(k) for k in keys])
    except ValueError as exc:
        raise TokenCryptoError(
            "TOKEN_ENCRYPTION_KEYS inválida (esperado: chave(s) Fernet base64)."
        ) from exc


def is_configured() -> bool:
    try:
        _fernet()
    except TokenCryptoError:
        return False
    return True


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise TokenCryptoError(
            "Token não decifra com as chaves atuais (chave trocada ou dado em texto puro?)."
        ) from exc


def rotate(token: str) -> str:
    """Recifra com a chave mais nova (a 1ª da lista)."""
    try:
        return _fernet().rotate(token.encode()).decode()
    except InvalidToken as exc:
        raise TokenCryptoError("Token não decifra com as chaves atuais.") from exc
