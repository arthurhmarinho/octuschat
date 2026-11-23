"""CRUD de usuários e dono de conta (precisa de TEST_DATABASE_URL)."""

import pytest
from sqlalchemy.exc import IntegrityError

from app import crud
from app.core.passwords import WeakPassword, verify_password
from app.crud.account import AccountOwnedByOther
from tests.conftest import requires_pg

pytestmark = requires_pg


async def test_email_normalizado_e_unico(pg_sessions):
    async with pg_sessions() as db:
        u = await crud.user.create(db, "  Fulano@Exemplo.COM ", "Fulano", "senha-bem-longa")
        assert u.email == "fulano@exemplo.com"
        assert u.must_change_password is True and u.is_admin is False
        found = await crud.user.get_by_email(db, "FULANO@exemplo.com")
        assert found is not None and found.id == u.id
    async with pg_sessions() as db:
        with pytest.raises(IntegrityError):
            await crud.user.create(db, "fulano@exemplo.com", "Outro", "senha-bem-longa")


async def test_senha_fraca_recusada(pg_sessions):
    async with pg_sessions() as db:
        with pytest.raises(WeakPassword):
            await crud.user.create(db, "a@x.com", "A", "curta")


async def test_set_password_zera_must_change(pg_sessions):
    async with pg_sessions() as db:
        u = await crud.user.create(db, "a@x.com", "A", "senha-bem-longa")
        await crud.user.set_password(db, u, "outra-senha-longa")
        assert u.must_change_password is False
        assert verify_password("outra-senha-longa", u.password_hash)
        assert not verify_password("senha-bem-longa", u.password_hash)


async def test_touch_login(pg_sessions):
    async with pg_sessions() as db:
        u = await crud.user.create(db, "a@x.com", "A", "senha-bem-longa")
        assert u.last_login_at is None
        await crud.user.touch_login(db, u)
        assert u.last_login_at is not None


async def test_upsert_grava_dono_em_conta_sem_dono(pg_sessions):
    async with pg_sessions() as db:
        a = await crud.user.create(db, "a@x.com", "A", "senha-bem-longa")
        # conta antiga, sem dono
        await crud.account.upsert(db, "ig1", "enc")
        acc = await crud.account.upsert(db, "ig1", "enc2", owner_user_id=a.id)
        assert acc.owner_user_id == a.id and acc.access_token_enc == "enc2"


async def test_upsert_recusa_conta_de_outro_dono(pg_sessions):
    async with pg_sessions() as db:
        a = await crud.user.create(db, "a@x.com", "A", "senha-bem-longa")
        b = await crud.user.create(db, "b@x.com", "B", "senha-bem-longa")
        await crud.account.upsert(db, "ig1", "enc", owner_user_id=a.id)
        with pytest.raises(AccountOwnedByOther):
            await crud.account.upsert(db, "ig1", "token-do-b", owner_user_id=b.id)
        # nada mudou
        acc = await crud.account.get(db, "ig1")
        assert acc.owner_user_id == a.id and acc.access_token_enc == "enc"
        # o próprio dono reconecta sem problema
        await crud.account.upsert(db, "ig1", "novo", owner_user_id=a.id)


async def test_get_owned_e_list_by_owner(pg_sessions):
    async with pg_sessions() as db:
        a = await crud.user.create(db, "a@x.com", "A", "senha-bem-longa")
        b = await crud.user.create(db, "b@x.com", "B", "senha-bem-longa")
        await crud.account.upsert(db, "a1", "e", owner_user_id=a.id)
        await crud.account.upsert(db, "b1", "e", owner_user_id=b.id)
        assert [x.ig_user_id for x in await crud.account.list_by_owner(db, a.id)] == ["a1"]
        assert await crud.account.get_owned(db, a.id, "a1") is not None
        assert await crud.account.get_owned(db, a.id, "b1") is None
        assert await crud.account.get_owned(db, a.id, "nao-existe") is None
