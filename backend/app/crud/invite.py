"""Operações de banco para convites (`user_invites`).

O token em texto só existe no retorno de `create`/`renew`; no banco vai o sha256.
`commit=False` deixa a escrita na transação do chamador (cadastro e redefinição
consomem o convite e mudam o usuário de uma vez só).
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invite import RESET, SIGNUP, UserInvite

TTL = {SIGNUP: timedelta(days=7), RESET: timedelta(hours=24)}


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _active():
    """Filtro de convite válido (não usado, não cancelado, não vencido)."""
    return (
        UserInvite.used_at.is_(None),
        UserInvite.revoked_at.is_(None),
        UserInvite.expires_at > func.now(),
    )


async def _finish(db: AsyncSession, commit: bool) -> None:
    if commit:
        await db.commit()
    else:
        await db.flush()


async def create(
    db: AsyncSession,
    purpose: str,
    *,
    name: str | None = None,
    email: str | None = None,
    ig_username: str | None = None,
    created_by_user_id: int | None = None,
    user_id: int | None = None,
    meta_tester_added_at: datetime | None = None,
    commit: bool = True,
) -> tuple[UserInvite, str]:
    """Cria o convite e devolve `(convite, token)`. O token não é recuperável depois."""
    raw = secrets.token_urlsafe(24)
    invite = UserInvite(
        token_hash=hash_token(raw),
        purpose=purpose,
        name=name,
        email=email.strip().lower() if email else None,
        ig_username=ig_username,
        created_by_user_id=created_by_user_id,
        user_id=user_id,
        meta_tester_added_at=meta_tester_added_at,
        expires_at=datetime.now(timezone.utc) + TTL[purpose],
    )
    db.add(invite)
    await _finish(db, commit)
    await db.refresh(invite)
    return invite, raw


async def get(db: AsyncSession, invite_id: int) -> UserInvite | None:
    # populate_existing: `revoke` & cia. são UPDATEs diretos; relê o estado atual.
    return await db.get(UserInvite, invite_id, populate_existing=True)


async def get_valid_by_token(db: AsyncSession, raw: str) -> UserInvite | None:
    result = await db.execute(
        select(UserInvite).where(UserInvite.token_hash == hash_token(raw), *_active())
    )
    return result.scalars().first()


async def consume(
    db: AsyncSession, raw: str, *, purpose: str | None = None, commit: bool = True
) -> UserInvite | None:
    """Marca o convite como usado, se ainda for válido. Atômico.

    É um único UPDATE: de duas chamadas concorrentes, só uma recebe o convite.
    Com `purpose`, um convite de outro tipo não é tocado.
    """
    where = [UserInvite.token_hash == hash_token(raw), *_active()]
    if purpose is not None:
        where.append(UserInvite.purpose == purpose)
    stmt = (
        update(UserInvite)
        .where(*where)
        .values(used_at=func.now())
        .returning(UserInvite)
        .execution_options(synchronize_session=False, populate_existing=True)
    )
    invite = (await db.execute(stmt)).scalars().first()
    if commit:
        await db.commit()
    return invite


async def revoke(db: AsyncSession, invite_id: int, *, commit: bool = True) -> bool:
    """Cancela um convite ainda não usado. False se não havia o que cancelar."""
    result = await db.execute(
        update(UserInvite)
        .where(
            UserInvite.id == invite_id,
            UserInvite.used_at.is_(None),
            UserInvite.revoked_at.is_(None),
        )
        .values(revoked_at=func.now())
    )
    if commit:
        await db.commit()
    return bool(result.rowcount)


async def revoke_active_resets(db: AsyncSession, user_id: int, *, commit: bool = True) -> None:
    """Invalida os links de redefinição ainda abertos do usuário."""
    await db.execute(
        update(UserInvite)
        .where(UserInvite.purpose == RESET, UserInvite.user_id == user_id, *_active())
        .values(revoked_at=func.now())
    )
    if commit:
        await db.commit()


async def find_pending_signup(db: AsyncSession, ig_username: str) -> UserInvite | None:
    result = await db.execute(
        select(UserInvite)
        .where(UserInvite.purpose == SIGNUP, UserInvite.ig_username == ig_username, *_active())
        .limit(1)
    )
    return result.scalars().first()


async def renew(db: AsyncSession, invite: UserInvite) -> tuple[UserInvite, str]:
    """Link novo para a mesma pessoa: revoga os ativos e copia os dados."""
    if invite.purpose == RESET:
        await revoke_active_resets(db, invite.user_id, commit=False)
    else:
        await db.execute(
            update(UserInvite)
            .where(
                UserInvite.purpose == SIGNUP,
                UserInvite.ig_username == invite.ig_username,
                *_active(),
            )
            .values(revoked_at=func.now())
        )
    # Um convite vencido não entra no filtro de ativos, mas é substituído também.
    await revoke(db, invite.id, commit=False)
    return await create(
        db,
        invite.purpose,
        name=invite.name,
        email=invite.email,
        ig_username=invite.ig_username,
        created_by_user_id=invite.created_by_user_id,
        user_id=invite.user_id,
        meta_tester_added_at=invite.meta_tester_added_at,
    )


async def mark_meta_added(db: AsyncSession, invite_id: int) -> UserInvite | None:
    """Marca o @ como adicionado na Meta (mantém a primeira data)."""
    invite = await get(db, invite_id)
    if invite is None or invite.revoked_at is not None or invite.purpose != SIGNUP:
        return None
    if invite.meta_tester_added_at is None:
        invite.meta_tester_added_at = datetime.now(timezone.utc)
        await db.commit()
    return invite


async def list_for_admin(db: AsyncSession) -> list[UserInvite]:
    """Todos os convites de cadastro não cancelados, do mais antigo ao mais novo."""
    result = await db.execute(
        select(UserInvite)
        .where(UserInvite.purpose == SIGNUP, UserInvite.revoked_at.is_(None))
        .order_by(UserInvite.created_at, UserInvite.id)
    )
    return list(result.scalars().all())


async def list_pending_signups(db: AsyncSession) -> list[UserInvite]:
    result = await db.execute(
        select(UserInvite)
        .where(UserInvite.purpose == SIGNUP, *_active())
        .order_by(UserInvite.created_at, UserInvite.id)
    )
    return list(result.scalars().all())


async def latest_signup_for_user(db: AsyncSession, user_id: int) -> UserInvite | None:
    """O convite de cadastro que o usuário usou (para saber o @ convidado)."""
    result = await db.execute(
        select(UserInvite)
        .where(UserInvite.purpose == SIGNUP, UserInvite.user_id == user_id)
        .order_by(UserInvite.created_at.desc(), UserInvite.id.desc())
        .limit(1)
    )
    return result.scalars().first()
