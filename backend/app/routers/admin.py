"""Administração do painel: convites, pessoas e links de redefinição.

Tudo aqui exige um admin. Excluir usuário e transferir contas do Instagram
entre usuários não existem (fora de escopo).
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.auth import require_admin
from app.core.config import settings
from app.core.config_check import config_problems
from app.core.database import get_session
from app.core.invite_fields import InvalidField, clean_email, clean_ig_username, clean_name
from app.models.invite import RESET, SIGNUP, UserInvite
from app.models.user import User
from app.schemas.account import AccountRead
from app.schemas.invite import (
    InviteCreated,
    InviteIn,
    InviteRead,
    PeopleRead,
    PersonAccount,
    PersonRead,
    ResetLinkRead,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

NOT_FOUND = "Convite não encontrado"


def _created(invite: UserInvite, token: str) -> InviteCreated:
    return InviteCreated(invite=InviteRead.model_validate(invite), token=token)


async def _open_signup(db: AsyncSession, invite_id: int) -> UserInvite:
    """Convite de cadastro ainda não usado nem cancelado (pode estar vencido)."""
    invite = await crud.invite.get(db, invite_id)
    if (
        invite is None
        or invite.purpose != SIGNUP
        or invite.used_at is not None
        or invite.revoked_at is not None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return invite


@router.post("/invites", response_model=InviteCreated, status_code=status.HTTP_201_CREATED)
async def create_invite(
    body: InviteIn,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    try:
        name = clean_name(body.name)
        email = clean_email(body.email) if (body.email or "").strip() else None
        ig_username = clean_ig_username(body.ig_username)
    except InvalidField as exc:
        raise HTTPException(422, str(exc)) from exc
    if email and await crud.user.get_by_email(db, email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Já existe uma conta com este e-mail")
    if await crud.invite.find_pending_signup(db, ig_username) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Já existe um convite pendente para @{ig_username}. Use “Copiar novo link”",
        )
    invite, token = await crud.invite.create(
        db,
        SIGNUP,
        name=name,
        email=email,
        ig_username=ig_username,
        created_by_user_id=admin.id,
    )
    return _created(invite, token)


@router.post("/invites/{invite_id}/meta-added", response_model=InviteRead)
async def meta_added(invite_id: int, db: AsyncSession = Depends(get_session)):
    """Vale também para o convite já usado: o dono pode marcar depois do cadastro."""
    invite = await crud.invite.mark_meta_added(db, invite_id)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    return invite


@router.post("/invites/{invite_id}/renew", response_model=InviteCreated)
async def renew_invite(invite_id: int, db: AsyncSession = Depends(get_session)):
    invite = await _open_signup(db, invite_id)
    return _created(*await crud.invite.renew(db, invite))


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invite(invite_id: int, db: AsyncSession = Depends(get_session)):
    await _open_signup(db, invite_id)
    await crud.invite.revoke(db, invite_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _user_status(accounts: list[PersonAccount]) -> str:
    if not accounts:
        return "awaiting_instagram"
    if any(a.needs_reconnect for a in accounts):
        return "needs_reconnect"
    return "active"


@router.get("/diagnostics")
async def diagnostics() -> dict[str, list[str]]:
    """Problemas de configuração do servidor (só o nome da variável e o que há)."""
    return {"problems": config_problems(settings)}


@router.get("/people", response_model=PeopleRead)
async def people(
    admin: User = Depends(require_admin), db: AsyncSession = Depends(get_session)
):
    """Um item por usuário e um por convite de cadastro ainda pendente."""
    owned: dict[int, list[PersonAccount]] = {}
    for account in await crud.account.list_all(db):
        if account.owner_user_id is None:
            continue
        read = AccountRead.model_validate(account)
        owned.setdefault(account.owner_user_id, []).append(
            PersonAccount(username=read.username, needs_reconnect=read.needs_reconnect)
        )
    # Do mais antigo ao mais novo: o último de cada usuário vence.
    used = {i.user_id: i for i in await crud.invite.list_for_admin(db) if i.user_id}

    items: list[PersonRead] = []
    for user in await crud.user.list_all(db):
        invite = used.get(user.id)
        accounts = owned.get(user.id, [])
        items.append(
            PersonRead(
                kind="user",
                status=_user_status(accounts),
                user_id=user.id,
                is_self=user.id == admin.id,
                name=user.name,
                email=user.email,
                ig_username=invite.ig_username if invite else None,
                accounts=accounts,
                last_login_at=user.last_login_at,
                invite_id=invite.id if invite else None,
                meta_tester_added=bool(invite and invite.meta_tester_added_at),
            )
        )
    for invite in await crud.invite.list_pending_signups(db):
        items.append(
            PersonRead(
                kind="invite",
                status="pending",
                name=invite.name,
                email=invite.email,
                ig_username=invite.ig_username,
                invite_id=invite.id,
                meta_tester_added=invite.meta_tester_added_at is not None,
                expires_at=invite.expires_at,
            )
        )
    app_id = settings.meta_app_id.strip()
    # Só devolve se parecer um ID: um valor errado (um segredo colado no campo
    # errado, por exemplo) não pode aparecer na tela.
    return PeopleRead(
        people=items,
        meta_app_id=app_id if re.fullmatch(r"\d{5,20}", app_id) else None,
    )


@router.post("/users/{user_id}/reset-link", response_model=ResetLinkRead)
async def reset_link(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    if user_id == admin.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Para a sua própria senha, use “Alterar senha”"
        )
    target = await crud.user.get(db, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    # Só o link mais novo vale.
    await crud.invite.revoke_active_resets(db, target.id, commit=False)
    invite, token = await crud.invite.create(
        db, RESET, user_id=target.id, created_by_user_id=admin.id
    )
    return ResetLinkRead(token=token, expires_at=invite.expires_at)
