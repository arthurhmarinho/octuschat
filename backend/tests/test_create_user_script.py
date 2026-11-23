"""scripts.create_user: convite, reset e claim-orphans (precisa de TEST_DATABASE_URL)."""

import pytest

from app import crud
from app.core.passwords import verify_password
from scripts.create_user import CliError, run
from tests.conftest import requires_pg

pytestmark = requires_pg


def _pw(lines: list[str]) -> str:
    return next(l for l in lines if l.startswith("Senha temporária")).split(": ", 1)[1]


async def test_cria_usuario_com_senha_temporaria(pg_sessions):
    async with pg_sessions() as db:
        lines = await run(db, email="B@x.com", name="Fulano", admin=False, claim=False, reset=False)
        user = await crud.user.get_by_email(db, "b@x.com")
        assert user.must_change_password and not user.is_admin
        assert verify_password(_pw(lines), user.password_hash)


async def test_claim_orphans_exige_admin(pg_sessions):
    async with pg_sessions() as db:
        with pytest.raises(CliError):
            await run(db, email="a@x.com", name="A", admin=False, claim=True, reset=False)


async def test_claim_orphans_passa_so_as_contas_sem_dono(pg_sessions):
    async with pg_sessions() as db:
        outro = await crud.user.create(db, "o@x.com", "O", "senha-bem-longa")
        await crud.account.upsert(db, "sem-dono-1", "e")
        await crud.account.upsert(db, "sem-dono-2", "e")
        await crud.account.upsert(db, "do-outro", "e", owner_user_id=outro.id)
        lines = await run(db, email="a@x.com", name="A", admin=True, claim=True, reset=False)
        admin = await crud.user.get_by_email(db, "a@x.com")
        assert admin.is_admin
        assert {a.ig_user_id for a in await crud.account.list_by_owner(db, admin.id)} == {
            "sem-dono-1", "sem-dono-2"
        }
        assert (await crud.account.get(db, "do-outro")).owner_user_id == outro.id
        assert any("2 conta(s)" in l for l in lines)


async def test_avisa_quando_ha_orfas_e_a_flag_nao_veio(pg_sessions):
    async with pg_sessions() as db:
        await crud.account.upsert(db, "sem-dono", "e")
        lines = await run(db, email="b@x.com", name="B", admin=False, claim=False, reset=False)
        assert any(l.startswith("Aviso") for l in lines)
        assert (await crud.account.get(db, "sem-dono")).owner_user_id is None


async def test_reset_password_gera_nova_senha_e_exige_troca(pg_sessions):
    async with pg_sessions() as db:
        u = await crud.user.create(db, "b@x.com", "B", "senha-bem-longa", must_change_password=False)
        lines = await run(db, email="b@x.com", name=None, admin=False, claim=False, reset=True)
        await db.refresh(u)
        assert u.must_change_password
        assert verify_password(_pw(lines), u.password_hash)
        assert not verify_password("senha-bem-longa", u.password_hash)


async def test_reset_de_usuario_inexistente_e_email_repetido(pg_sessions):
    async with pg_sessions() as db:
        with pytest.raises(CliError):
            await run(db, email="nao@x.com", name=None, admin=False, claim=False, reset=True)
        await crud.user.create(db, "b@x.com", "B", "senha-bem-longa")
        with pytest.raises(CliError):
            await run(db, email="b@x.com", name="B", admin=False, claim=False, reset=False)


async def test_nome_obrigatorio_ao_criar(pg_sessions):
    async with pg_sessions() as db:
        with pytest.raises(CliError):
            await run(db, email="b@x.com", name=None, admin=False, claim=False, reset=False)
