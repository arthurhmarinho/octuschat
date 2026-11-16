"""Cifra os tokens de acesso (Fernet): access_token → access_token_enc.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-15

Exige TOKEN_ENCRYPTION_KEYS no ambiente — sem ela a migração falha ANTES de
alterar qualquer coisa (e o Postgres desfaz tudo: DDL transacional).

Idempotente: valores que já decifram com as chaves atuais não são recifrados.
O downgrade decifra de volta para texto puro e restaura o nome da coluna.

Usa Fernet direto (não app.core.crypto) para a migração não mudar se o código
do app mudar no futuro.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _fernet() -> MultiFernet:
    keys = [k.strip() for k in settings.token_encryption_keys.split(",") if k.strip()]
    if not keys:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEYS não configurada — necessária para cifrar os tokens."
        )
    return MultiFernet([Fernet(k) for k in keys])


def _rows(column: str):
    return op.get_bind().execute(
        sa.text(f"SELECT ig_user_id, {column} FROM instagram_accounts")
    ).all()


def _set(column: str, ig_user_id: str, value: str) -> None:
    op.get_bind().execute(
        sa.text(f"UPDATE instagram_accounts SET {column} = :v WHERE ig_user_id = :id"),
        {"v": value, "id": ig_user_id},
    )


def upgrade() -> None:
    f = _fernet()  # falha cedo se a chave faltar/for inválida
    op.alter_column(
        "instagram_accounts", "access_token", new_column_name="access_token_enc"
    )
    for ig_user_id, value in _rows("access_token_enc"):
        try:
            f.decrypt(value.encode())
            continue  # já cifrado
        except InvalidToken:
            pass
        _set("access_token_enc", ig_user_id, f.encrypt(value.encode()).decode())


def downgrade() -> None:
    f = _fernet()
    for ig_user_id, value in _rows("access_token_enc"):
        try:
            plain = f.decrypt(value.encode()).decode()
        except InvalidToken:
            continue  # já está em texto puro
        _set("access_token_enc", ig_user_id, plain)
    op.alter_column(
        "instagram_accounts", "access_token_enc", new_column_name="access_token"
    )
