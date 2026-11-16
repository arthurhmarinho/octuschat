"""Compara o schema de um banco com os models — SOMENTE LEITURA.

Uso (antes de `alembic stamp` num banco que já existe, ex.: Supabase):

    python -m scripts.check_schema

Usa MIGRATIONS_DATABASE_URL (ou DATABASE_URL). Não grava nada no banco.
Sai com código 0 se não houver diferenças, 1 caso contrário.

Além do diff do Alembic (tabelas, colunas, tipos, índices, FKs), confere os
labels do enum `trigger_type`, que o autogenerate não compara.
"""

import asyncio
import pprint
import sys

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app import models  # noqa: F401
from app.core.config import settings
from app.core.database import Base
from app.models.automation import TriggerType

IGNORED_TABLES = {"alembic_version"}

# Labels que existem em produção mas não no modelo: sobras minúsculas de um
# ALTER TYPE manual, sem nenhuma linha usando. A baseline (0001) os reproduz.
LEGACY_ENUM_LABELS = {"dm_keyword", "dm_any"}


def _diff(connection) -> list:
    ctx = MigrationContext.configure(
        connection,
        opts={
            "compare_type": True,
            "include_name": lambda name, type_, _parent: not (
                type_ == "table" and name in IGNORED_TABLES
            ),
        },
    )
    return compare_metadata(ctx, Base.metadata)


async def main() -> int:
    url = settings.migrations_database_url or settings.database_url
    engine = create_async_engine(url, connect_args={"prepare_threshold": None})
    problems = 0
    async with engine.connect() as conn:
        diffs = await conn.run_sync(_diff)
        if diffs:
            problems += len(diffs)
            print("Diferenças entre o banco e os models:")
            pprint.pprint(diffs)

        rows = await conn.execute(
            text(
                "SELECT e.enumlabel FROM pg_enum e "
                "JOIN pg_type t ON t.oid = e.enumtypid "
                "WHERE t.typname = 'trigger_type' ORDER BY e.enumsortorder"
            )
        )
        in_db = [r[0] for r in rows]
        expected = [m.name for m in TriggerType]
        missing = [x for x in expected if x not in in_db]
        extra = [x for x in in_db if x not in expected and x not in LEGACY_ENUM_LABELS]
        if missing or extra:
            problems += 1
            print(f"Enum trigger_type: faltando {missing}, sobrando {extra} (banco: {in_db})")
    await engine.dispose()

    if problems:
        print(f"\n{problems} diferença(s). Não faça o stamp ainda.")
        return 1
    print("Schema confere com os models.")
    print("Banco legado (sem tabela alembic_version)? Marque com: alembic stamp 0001")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
