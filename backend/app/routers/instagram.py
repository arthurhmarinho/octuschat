"""OAuth da Meta para conectar uma conta do Instagram."""

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.auth import current_user, make_oauth_state, verify_oauth_state
from app.core.config import settings
from app.core.security import redact_secrets
from app.core.database import get_session
from app.core.ownership import owned_account
from app.crud.account import AccountOwnedByOther
from app.models.user import User
from app.schemas.account import AccountRead
from app.services import instagram_api, token_service

logger = logging.getLogger("inboxpilot.instagram")
router = APIRouter(prefix="/instagram", tags=["instagram"])

# Todas as rotas exigem segredo + usuário (`current_user`), exceto `/callback`
# (a Meta redireciona o browser direto para ele; protegido pelo `state`
# assinado, que carrega o id de quem iniciou a conexão).

SCOPES = ",".join(
    [
        "instagram_business_basic",
        "instagram_business_manage_messages",
        "instagram_business_manage_comments",
    ]
)


@router.get("/connect")
async def connect(user: User = Depends(current_user)):
    """Redireciona para a tela de autorização da Meta.

    Acessado via proxy do Next (`/api/backend/instagram/connect`), que repassa
    o redirect ao browser.
    """
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.oauth_redirect_uri,
        "scope": SCOPES,
        "response_type": "code",
        "state": make_oauth_state(user.id),
    }
    return RedirectResponse(
        f"https://www.instagram.com/oauth/authorize?{urlencode(params)}"
    )


@router.get("/callback")
async def callback(
    code: str = "", state: str = "", db: AsyncSession = Depends(get_session)
):
    """Troca o `code` por access token e persiste a conta.

    Rota pública: a Meta redireciona o browser para cá. O `state` assinado
    garante que o fluxo foi iniciado por nós (via `/connect` autenticado).
    """
    owner_id = verify_oauth_state(state)
    if owner_id is None:
        logger.warning("OAuth callback com state inválido/expirado — rejeitado.")
        return RedirectResponse(f"{settings.frontend_url}?connected=error")
    if await crud.user.get(db, owner_id) is None:
        logger.warning("OAuth callback de usuário inexistente (%s) — rejeitado.", owner_id)
        return RedirectResponse(f"{settings.frontend_url}?connected=error")
    if not code:
        return RedirectResponse(f"{settings.frontend_url}?connected=error")

    data = {
        "client_id": settings.meta_app_id,
        "client_secret": settings.meta_app_secret,
        "grant_type": "authorization_code",
        "redirect_uri": settings.oauth_redirect_uri,
        "code": code,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            "https://api.instagram.com/oauth/access_token", data=data
        )
        resp.raise_for_status()
        payload = resp.json()

    ig_user_id = str(payload.get("user_id", ""))
    access_token = payload.get("access_token", "")

    if not (ig_user_id and access_token):
        return RedirectResponse(f"{settings.frontend_url}?connected=error")

    # Troca o token curto (~1h) pelo de longa duração (~60 dias).
    expires_at = None
    try:
        longlived = await instagram_api.exchange_for_long_lived(access_token)
        access_token = longlived.get("access_token", access_token)
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=longlived.get("expires_in", 0)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao trocar por token longo: %s", exc)

    # Busca perfil: username + o `id` (usado no webhook, difere do user_id).
    username = None
    ig_id = None
    try:
        profile = await instagram_api.get_profile(ig_user_id, access_token)
        username = profile.get("username")
        # No /me, é o campo `user_id` que corresponde ao entry.id do webhook.
        ig_id = profile.get("user_id")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Não consegui buscar o perfil: %s", exc)

    try:
        account = await crud.account.upsert(
            db,
            ig_user_id=ig_user_id,
            access_token_enc=token_service.encrypt_token(access_token),
            username=username,
            token_expires_at=expires_at,
            ig_id=ig_id,
            owner_user_id=owner_id,
        )
    except AccountOwnedByOther:
        logger.warning("Conta IG %s já pertence a outro usuário — recusada.", ig_user_id)
        return RedirectResponse(f"{settings.frontend_url}?connected=error&reason=owned")
    # Token novo: some a marca de "Meta recusou o token" (código 190).
    if account.token_invalid_at is not None:
        account.token_invalid_at = None
        await db.commit()

    # Inscreve o app nos webhooks da conta (comentários + mensagens).
    try:
        await instagram_api.subscribe_webhooks(ig_user_id, access_token)
        logger.info("Webhooks inscritos para %s.", ig_user_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falha ao inscrever webhooks: %s", exc)

    logger.info("Conta IG %s (%s) conectada.", ig_user_id, username)
    return RedirectResponse(f"{settings.frontend_url}?connected=ok")


@router.get("/accounts", response_model=list[AccountRead])
async def list_accounts(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_session)
):
    return await crud.account.list_by_owner(db, user.id)


@router.get("/{account_id}/subscription")
async def account_subscription(
    account_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    """Diagnóstico: campos de webhook aos quais a conta está inscrita.

    Também tenta (re)inscrever, retornando o resultado — útil se a inscrição
    do OAuth falhou silenciosamente.
    """
    # Aceita o ig_user_id OU o ig_id (id do webhook), mas só se a conta for do usuário.
    account = await crud.account.get_by_any_id(db, account_id)
    if account is None or account.owner_user_id != user.id:
        raise HTTPException(404, "Conta do Instagram não conectada")
    token = await token_service.get_valid_token(db, account)
    result: dict = {"ig_user_id": account.ig_user_id, "ig_id": account.ig_id}

    # Backfill do ig_id (id usado no webhook) sem precisar reconectar.
    try:
        profile = await instagram_api.get_profile(account.ig_user_id, token)
        result["profile"] = profile
        # `user_id` do /me = entry.id do webhook (difere do `id`/ig_user_id).
        webhook_id = profile.get("user_id")
        if webhook_id and webhook_id != account.ig_id:
            account.ig_id = webhook_id
            await db.commit()
            result["ig_id_updated"] = account.ig_id
    except Exception as exc:  # noqa: BLE001
        result["profile_error"] = redact_secrets(str(exc))

    try:
        result["subscribe_now"] = await instagram_api.subscribe_webhooks(
            account.ig_user_id, token
        )
    except Exception as exc:  # noqa: BLE001
        result["subscribe_error"] = redact_secrets(str(exc))
    try:
        result["current"] = await instagram_api.get_subscribed_apps(
            account.ig_user_id, token
        )
    except Exception as exc:  # noqa: BLE001
        result["get_error"] = redact_secrets(str(exc))
    return result


@router.get("/{account_id}/media")
async def list_account_media(
    account_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    """Publicações/Reels da conta — para o seletor de post no builder."""
    account = await owned_account(account_id, user, db)
    try:
        token = await token_service.get_valid_token(db, account)
        return await instagram_api.list_media(account.ig_user_id, token)
    except Exception as exc:  # noqa: BLE001
        await token_service.note_api_error(db, account, exc)
        # Ex.: token inválido (conta demo) — frontend cai no fallback manual.
        raise HTTPException(502, f"Falha ao buscar mídia: {redact_secrets(str(exc))}")
