"""Cria usuários do painel e redefine senhas pela linha de comando.

O caminho normal agora é o PAINEL: Configurações → Pessoas gera o link de
convite (a pessoa cria a própria conta) e o link de redefinição de senha. Este
script fica para criar o PRIMEIRO admin e para emergências (ex.: o próprio
admin esqueceu a senha).

Exemplos (a partir de `backend/`, com o `.env` do ambiente alvo):

    python -m scripts.create_user --email dono@x.com --name "Arthur" --admin --claim-orphans
    python -m scripts.create_user --email testador@x.com --name "Fulano"
    python -m scripts.create_user --email testador@x.com --reset-password

Gera uma senha temporária forte, imprime UMA vez e grava com
`must_change_password = true` (a pessoa troca no primeiro acesso).

`--claim-orphans` passa as contas do Instagram sem dono para este usuário.
Só vale junto com `--admin`. Se existirem contas sem dono e a flag não vier,
o script avisa.

Usa MIGRATIONS_DATABASE_URL (ou DATABASE_URL), como os outros scripts.
"""

import argparse
import asyncio
import secrets
import sys

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import crud
from app.core.config import settings
from app.models.account import InstagramAccount
from app.models.user import User


class CliError(Exception):
    """Erro de uso: a mensagem vai para o stderr."""


def temp_password() -> str:
    return secrets.token_urlsafe(12)


async def count_orphans(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(InstagramAccount).where(
            InstagramAccount.owner_user_id.is_(None)
        )
    )
    return int(result.scalar_one())


async def claim_orphans(db: AsyncSession, user: User) -> int:
    result = await db.execute(
        update(InstagramAccount)
        .where(InstagramAccount.owner_user_id.is_(None))
        .values(owner_user_id=user.id)
    )
    await db.commit()
    return result.rowcount or 0


async def run(
    db: AsyncSession,
    *,
    email: str,
    name: str | None,
    admin: bool,
    claim: bool,
    reset: bool,
) -> list[str]:
    """Executa o pedido e devolve as linhas a imprimir (sem tocar no stdout)."""
    if claim and not admin:
        raise CliError("--claim-orphans só é aceito junto com --admin")
    if reset and (admin or claim):
        raise CliError("--reset-password não combina com --admin / --claim-orphans")

    out: list[str] = []
    existing = await crud.user.get_by_email(db, email)

    if reset:
        if existing is None:
            raise CliError(f"Usuário {email} não existe")
        pw = temp_password()
        await crud.user.set_password(db, existing, pw, must_change=True)
        out.append(f"Senha temporária de {existing.email}: {pw}")
        out.append("Ela aparece só desta vez. A pessoa troca no primeiro acesso.")
        return out

    if existing is not None:
        # Único caso aceito para um e-mail que já existe: um admin reivindicando órfãs.
        if claim and existing.is_admin:
            n = await claim_orphans(db, existing)
            return [f"{existing.email} já existe. {n} conta(s) sem dono passaram para ele."]
        raise CliError(f"Já existe um usuário com o e-mail {existing.email}. "
                       "Use --reset-password para gerar uma nova senha temporária")

    if not name or not name.strip():
        raise CliError("--name é obrigatório ao criar um usuário")

    pw = temp_password()
    user = await crud.user.create(db, email, name, pw, is_admin=admin, must_change_password=True)
    out.append(f"Usuário criado: {user.email} ({'admin' if admin else 'comum'})")
    out.append(f"Senha temporária: {pw}")
    out.append("Ela aparece só desta vez. A pessoa troca no primeiro acesso.")

    if claim:
        n = await claim_orphans(db, user)
        out.append(f"{n} conta(s) do Instagram sem dono passaram para {user.email}.")
    else:
        orphans = await count_orphans(db)
        if orphans:
            out.append(
                f"Aviso: há {orphans} conta(s) do Instagram sem dono. "
                "Rode de novo com --admin --claim-orphans no usuário que deve ficar com elas."
            )
    return out


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Cria usuários do painel e redefine senhas.")
    p.add_argument("--email", required=True)
    p.add_argument("--name")
    p.add_argument("--admin", action="store_true")
    p.add_argument("--claim-orphans", action="store_true", dest="claim")
    p.add_argument("--reset-password", action="store_true", dest="reset")
    return p


async def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    url = settings.migrations_database_url or settings.database_url
    engine = create_async_engine(url, connect_args={"prepare_threshold": None})
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            lines = await run(
                db, email=args.email, name=args.name, admin=args.admin,
                claim=args.claim, reset=args.reset,
            )
    except CliError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:  # senha/política
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
