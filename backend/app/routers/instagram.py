"""OAuth da Meta para conectar uma conta do Instagram."""

import logging
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.core.database import get_session
from app.schemas.account import AccountRead
from app.services import instagram_api

logger = logging.getLogger("inboxpilot.instagram")
router = APIRouter(prefix="/instagram", tags=["instagram"])

SCOPES = ",".join(
    [
        "instagram_business_basic",
        "instagram_business_manage_messages",
        "instagram_business_manage_comments",
    ]
)


@router.get("/connect")
async def connect():
    """Redireciona para a tela de autorização da Meta."""
    params = {
        "client_id": settings.meta_app_id,
        "redirect_uri": settings.oauth_redirect_uri,
        "scope": SCOPES,
        "response_type": "code",
    }
    return RedirectResponse(
        f"https://www.instagram.com/oauth/authorize?{urlencode(params)}"
    )


@router.get("/callback")
async def callback(code: str = "", db: AsyncSession = Depends(get_session)):
    """Troca o `code` por access token e persiste a conta."""
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

    # Busca o username pra exibição (best-effort).
    username = None
    try:
        profile = await instagram_api.get_profile(ig_user_id, access_token)
        username = profile.get("username")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Não consegui buscar o perfil: %s", exc)

    await crud.account.upsert(
        db, ig_user_id=ig_user_id, access_token=access_token, username=username
    )
    logger.info("Conta IG %s (%s) conectada.", ig_user_id, username)
    return RedirectResponse(f"{settings.frontend_url}?connected=ok")


@router.get("/accounts", response_model=list[AccountRead])
async def list_accounts(db: AsyncSession = Depends(get_session)):
    return await crud.account.list_all(db)


@router.get("/{account_id}/media")
async def list_account_media(
    account_id: str, db: AsyncSession = Depends(get_session)
):
    """Publicações/Reels da conta — para o seletor de post no builder."""
    account = await crud.account.get(db, account_id)
    if account is None:
        raise HTTPException(404, "Conta do Instagram não conectada")
    try:
        return await instagram_api.list_media(
            account.ig_user_id, account.access_token
        )
    except Exception as exc:  # noqa: BLE001
        # Ex.: token inválido (conta demo) — frontend cai no fallback manual.
        raise HTTPException(502, f"Falha ao buscar mídia: {exc}")
