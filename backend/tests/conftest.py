import pytest
from cryptography.fernet import Fernet

from app.core.config import settings


@pytest.fixture
def fernet_key(monkeypatch) -> str:
    """Configura TOKEN_ENCRYPTION_KEYS com uma chave nova para o teste."""
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "token_encryption_keys", key)
    return key


import os

TEST_DB = os.environ.get("TEST_DATABASE_URL")
requires_pg = pytest.mark.skipif(not TEST_DB, reason="TEST_DATABASE_URL não definida")


@pytest.fixture
async def pg_sessions():
    """Sessões contra o Postgres descartável (schema recriado pelos models)."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app import models  # noqa: F401
    from app.core.database import Base

    engine = create_async_engine(
        TEST_DB, poolclass=NullPool, connect_args={"prepare_threshold": None}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        await conn.execute(text("DROP TYPE IF EXISTS trigger_type"))
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()
