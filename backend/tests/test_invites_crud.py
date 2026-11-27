"""CRUD de convites (precisa de TEST_DATABASE_URL)."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import crud
from app.models.invite import UserInvite
from tests.conftest import requires_pg

pytestmark = requires_pg


async def make(db, **kw):
    kw.setdefault("ig_username", "fulano")
    return await crud.invite.create(db, kw.pop("purpose", "signup"), **kw)


async def expire(db, invite):
    invite.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()


async def test_token_so_existe_como_hash(pg_sessions):
    async with pg_sessions() as db:
        invite, raw = await make(db, name="Fulano", email=" Fulano@X.com ")
        assert len(raw) >= 32 and invite.token_hash == crud.invite.hash_token(raw)
        assert invite.token_hash != raw and invite.email == "fulano@x.com"
        row = (await db.execute(text("select * from user_invites"))).mappings().one()
        assert raw not in [str(v) for v in row.values()]
        assert (await crud.invite.get_valid_by_token(db, raw)).id == invite.id
        assert await crud.invite.get_valid_by_token(db, invite.token_hash) is None


@pytest.mark.parametrize("purpose,ttl", [("signup", timedelta(days=7)), ("reset", timedelta(hours=24))])
async def test_validade_depende_do_tipo(pg_sessions, purpose, ttl):
    async with pg_sessions() as db:
        invite, _ = await make(db, purpose=purpose)
        left = invite.expires_at - datetime.now(timezone.utc)
        assert ttl - timedelta(minutes=1) < left <= ttl


async def test_purpose_desconhecido_o_banco_recusa(pg_sessions):
    async with pg_sessions() as db:
        db.add(UserInvite(token_hash="x" * 64, purpose="outro",
                          expires_at=datetime.now(timezone.utc)))
        with pytest.raises(IntegrityError):
            await db.commit()


async def test_vencido_nao_vale(pg_sessions):
    async with pg_sessions() as db:
        invite, raw = await make(db)
        await expire(db, invite)
        assert await crud.invite.get_valid_by_token(db, raw) is None
        assert await crud.invite.consume(db, raw) is None
        assert await crud.invite.list_pending_signups(db) == []


async def test_uso_unico(pg_sessions):
    async with pg_sessions() as db:
        _, raw = await make(db)
        used = await crud.invite.consume(db, raw)
        assert used is not None and used.used_at is not None
        assert await crud.invite.consume(db, raw) is None
        assert await crud.invite.get_valid_by_token(db, raw) is None


async def test_duas_chamadas_concorrentes_so_uma_ganha(pg_sessions):
    async with pg_sessions() as db:
        _, raw = await make(db)
    async with pg_sessions() as first, pg_sessions() as second:
        # A 1ª consome e segura a transação; a 2ª fica esperando a linha.
        winner = await crud.invite.consume(first, raw, commit=False)
        loser = asyncio.create_task(crud.invite.consume(second, raw))
        await asyncio.sleep(0.2)
        assert not loser.done()
        await first.commit()
        assert winner is not None and await loser is None


async def test_rollback_devolve_o_convite(pg_sessions):
    async with pg_sessions() as db:
        _, raw = await make(db)
        assert await crud.invite.consume(db, raw, commit=False) is not None
        await db.rollback()
        assert await crud.invite.get_valid_by_token(db, raw) is not None


async def test_consume_de_outro_tipo_nao_gasta(pg_sessions):
    async with pg_sessions() as db:
        _, raw = await make(db)
        assert await crud.invite.consume(db, raw, purpose="reset") is None
        assert await crud.invite.consume(db, raw, purpose="signup") is not None


async def test_revogacao(pg_sessions):
    async with pg_sessions() as db:
        invite, raw = await make(db)
        assert await crud.invite.revoke(db, invite.id) is True
        assert await crud.invite.consume(db, raw) is None
        assert await crud.invite.revoke(db, invite.id) is False
        assert await crud.invite.list_for_admin(db) == []
        assert await crud.invite.mark_meta_added(db, invite.id) is None


async def test_renew_invalida_o_antigo_e_copia_os_dados(pg_sessions):
    async with pg_sessions() as db:
        invite, old = await make(db, name="Fulano", email="f@x.com")
        await crud.invite.mark_meta_added(db, invite.id)
        _, other = await make(db, ig_username="outra_pessoa")
        fresh, new = await crud.invite.renew(db, invite)
        assert new != old and await crud.invite.get_valid_by_token(db, old) is None
        assert await crud.invite.get_valid_by_token(db, new) is not None
        assert await crud.invite.get_valid_by_token(db, other) is not None
        assert (fresh.name, fresh.email, fresh.ig_username) == ("Fulano", "f@x.com", "fulano")
        assert fresh.meta_tester_added_at == invite.meta_tester_added_at is not None


async def test_latest_signup_e_apagado_junto_com_o_usuario(pg_sessions):
    async with pg_sessions() as db:
        user = await crud.user.create(db, "u@x.com", "U", "senha-bem-grande")
        assert await crud.invite.latest_signup_for_user(db, user.id) is None
        invite, _ = await make(db, user_id=user.id)
        await make(db, purpose="reset", user_id=user.id, ig_username=None)
        assert (await crud.invite.latest_signup_for_user(db, user.id)).id == invite.id
        await db.delete(user)
        await db.commit()
        assert (await db.execute(text("select count(*) from user_invites"))).scalar_one() == 0
