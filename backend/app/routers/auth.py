"""Login, cadastro por convite e identidade do usuário do painel.

Chamado só pelo Next (com o segredo da API). O browser nunca vê o backend: o
Next grava a sessão com o id devolvido aqui. Convite, cadastro e redefinição
não têm usuário logado — quem autoriza é o token do link.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.auth import current_user, require_api_secret
from app.core.database import get_session
from app.core.invite_fields import InvalidField, clean_email, clean_name
from app.core.passwords import (
    WeakPassword,
    check_policy,
    hash_password,
    verify_password,
)
from app.models.invite import RESET, SIGNUP
from app.models.user import User
from app.schemas.invite import InviteInfo, OnboardingRead, RegisterIn, ResetIn
from app.schemas.user import LoginIn, PasswordChangeIn, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

# Mesmo detail para e-mail inexistente e senha errada (não revela quem tem conta).
BAD_LOGIN = "E-mail ou senha incorretos"
GONE = "Este convite não vale mais"
EMAIL_TAKEN = "Já existe uma conta com este e-mail. Entre com ela"
# Hash de uma senha qualquer: serve para gastar o mesmo tempo quando o e-mail
# não existe (evita distinguir pelo tempo de resposta).
_DUMMY_HASH = hash_password("senha-que-nunca-sera-usada")


@router.post("/login", response_model=UserRead, dependencies=[Depends(require_api_secret)])
async def login(body: LoginIn, db: AsyncSession = Depends(get_session)):
    user = await crud.user.get_by_email(db, body.email)
    ok = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, BAD_LOGIN)
    await crud.user.touch_login(db, user)
    return user


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(current_user)):
    return user


@router.post("/password", response_model=UserRead)
async def change_password(
    body: PasswordChangeIn,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Senha atual incorreta")
    try:
        await crud.user.set_password(db, user, body.new_password, must_change=False)
    except WeakPassword as exc:
        raise HTTPException(422, str(exc)) from exc
    return user


# ── Convite, cadastro e redefinição ─────────────────────────


@router.get(
    "/invites/{token}",
    response_model=InviteInfo,
    dependencies=[Depends(require_api_secret)],
)
async def invite_info(token: str, db: AsyncSession = Depends(get_session)):
    """Inexistente, vencido, usado e cancelado respondem igual: `valid: false`."""
    invite = await crud.invite.get_valid_by_token(db, token)
    if invite is None:
        return InviteInfo()
    name, email = invite.name, invite.email
    if invite.purpose == RESET:
        target = await crud.user.get(db, invite.user_id)
        if target is None:
            return InviteInfo()
        name, email = target.name, target.email
    return InviteInfo(
        valid=True,
        purpose=invite.purpose,
        name=name,
        email=email,
        ig_username=invite.ig_username,
    )


@router.post("/register", response_model=UserRead, dependencies=[Depends(require_api_secret)])
async def register(body: RegisterIn, db: AsyncSession = Depends(get_session)):
    # Tudo que pode ser recusado vem ANTES de gastar o convite.
    try:
        check_policy(body.password)
        name = clean_name(body.name)
        email = clean_email(body.email)
    except (WeakPassword, InvalidField) as exc:
        raise HTTPException(422, str(exc)) from exc
    # O convite é conferido antes do e-mail: sem um link válido, esta rota não
    # revela quem tem conta.
    pending = await crud.invite.get_valid_by_token(db, body.token)
    if pending is None or pending.purpose != SIGNUP:
        raise HTTPException(status.HTTP_410_GONE, GONE)
    if await crud.user.get_by_email(db, email) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN)

    # Convite e usuário na mesma transação: ou os dois, ou nenhum.
    invite = await crud.invite.consume(db, body.token, purpose=SIGNUP, commit=False)
    if invite is None:
        await db.rollback()
        raise HTTPException(status.HTTP_410_GONE, GONE)
    try:
        user = await crud.user.create(
            db, email, name, body.password, must_change_password=False, commit=False
        )
    except IntegrityError as exc:  # outro cadastro com o mesmo e-mail ganhou a corrida
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, EMAIL_TAKEN) from exc
    invite.user_id = user.id
    user.last_login_at = datetime.now(timezone.utc)  # o cadastro já entra
    await db.commit()
    return user


@router.post("/reset", response_model=UserRead, dependencies=[Depends(require_api_secret)])
async def reset_password(body: ResetIn, db: AsyncSession = Depends(get_session)):
    try:
        check_policy(body.password)
    except WeakPassword as exc:
        raise HTTPException(422, str(exc)) from exc
    invite = await crud.invite.consume(db, body.token, purpose=RESET, commit=False)
    user = await crud.user.get(db, invite.user_id) if invite else None
    if user is None:
        await db.rollback()
        raise HTTPException(status.HTTP_410_GONE, GONE)
    await crud.user.set_password(db, user, body.password, must_change=False, commit=False)
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    return user


@router.get("/onboarding", response_model=OnboardingRead)
async def onboarding(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_session)
):
    """O que o assistente /conectar sabe de verdade sobre quem está logado."""
    invite = await crud.invite.latest_signup_for_user(db, user.id)
    return OnboardingRead(
        invited_ig_username=invite.ig_username if invite else None,
        meta_tester_added=bool(invite and invite.meta_tester_added_at),
        accounts=await crud.account.list_by_owner(db, user.id),
    )
