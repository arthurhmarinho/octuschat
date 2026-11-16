"""Ambiente do Alembic (async, psycopg3).

A URL vem das settings do app: MIGRATIONS_DATABASE_URL se definida (use a
conexão *session pooler*, porta 5432, do Supabase), senão DATABASE_URL.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app import models  # noqa: F401  (registra os modelos no metadata)
from app.core.config import settings
from app.core.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return settings.migrations_database_url or settings.database_url


def run_migrations_offline() -> None:
    """Gera SQL sem conectar (`alembic upgrade head --sql`)."""
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    # prepare_threshold=None: o pooler do Supabase não suporta prepared statements.
    engine = create_async_engine(_url(), connect_args={"prepare_threshold": None})
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
