"""Configuração do SQLAlchemy assíncrono (asyncpg + Supabase Postgres)."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Base declarativa para todos os modelos ORM."""


def _engine_kwargs() -> dict:
    """Monta kwargs do engine conforme o driver (Postgres vs SQLite)."""
    url = settings.database_url
    kwargs: dict = {"echo": settings.db_echo, "pool_pre_ping": True}

    if url.startswith("postgresql"):
        # `prepare_threshold=None` desabilita prepared statements do psycopg —
        # necessário com o pooler do Supabase em modo *transaction* (pgbouncer
        # não os suporta). Pool modesto: o servidor é sempre-on (Railway/Render).
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 5
        kwargs["connect_args"] = {"prepare_threshold": None}

    return kwargs


engine = create_async_engine(settings.database_url, **_engine_kwargs())

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency do FastAPI: fornece uma sessão por request."""
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Cria as tabelas (dev/demo). Em produção, prefira migrações Alembic."""
    # importa os modelos para registrá-los no metadata antes do create_all
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
