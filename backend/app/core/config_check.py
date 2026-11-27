"""Checagem da configuração na inicialização (função pura).

Cada problema é uma frase curta, só com o NOME da variável e o que está errado.
Nunca inclua o valor: a lista vai para o log e para a tela do admin.
"""

import re

from cryptography.fernet import Fernet

from app.core.config import Settings

DEFAULT_VERIFY_TOKEN = "troque-este-valor"


def _fernet_keys_ok(raw: str) -> bool:
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    try:
        for key in keys:
            Fernet(key)
    except ValueError:
        return False
    return bool(keys)


def config_problems(settings: Settings) -> list[str]:
    problems: list[str] = []

    app_id = settings.meta_app_id
    if not app_id:
        problems.append("META_APP_ID está vazio")
    elif not re.fullmatch(r"[0-9]{5,20}", app_id):
        problems.append("META_APP_ID não é um ID da Meta (o ID do app do Instagram tem só números)")

    if not settings.meta_app_secret.strip():
        problems.append("META_APP_SECRET está vazio")

    redirect = settings.oauth_redirect_uri
    if settings.is_production and not redirect.startswith("https://"):
        problems.append("OAUTH_REDIRECT_URI precisa começar com https:// em produção")
    if not redirect.endswith("/instagram/callback"):
        problems.append("OAUTH_REDIRECT_URI precisa terminar em /instagram/callback")

    if settings.webhook_verify_token == DEFAULT_VERIFY_TOKEN:
        problems.append("WEBHOOK_VERIFY_TOKEN ainda está com o valor de exemplo")

    if not settings.token_encryption_keys.strip():
        problems.append("TOKEN_ENCRYPTION_KEYS está vazio")
    elif not _fernet_keys_ok(settings.token_encryption_keys):
        problems.append("TOKEN_ENCRYPTION_KEYS é inválido (esperado: chave Fernet em base64)")

    if not settings.api_secret:
        problems.append("API_SECRET está vazio: as rotas protegidas respondem 401")

    return problems
