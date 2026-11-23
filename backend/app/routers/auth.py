"""Login e identidade do usuário do painel.

Chamado só pelo route handler do Next (com o segredo da API). O browser nunca
vê esta rota: o Next grava a sessão com o id devolvido aqui.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.auth import current_user, require_api_secret
from app.core.database import get_session
from app.core.passwords import WeakPassword, hash_password, verify_password
from app.models.user import User
from app.schemas.user import LoginIn, PasswordChangeIn, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])

# Mesmo detail para e-mail inexistente e senha errada (não revela quem tem conta).
BAD_LOGIN = "E-mail ou senha incorretos"
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
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return user
