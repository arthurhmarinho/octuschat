"""OAuth da Meta para conectar uma conta do Instagram."""

import logging
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.config import settings
from app.core.database import get_session
from app.schemas.account import AccountRead

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

    await crud.account.upsert(db, ig_user_id=ig_user_id, access_token=access_token)
    logger.info("Conta IG %s conectada.", ig_user_id)
    return RedirectResponse(f"{settings.frontend_url}?connected=ok")


@router.get("/accounts", response_model=list[AccountRead])
async def list_accounts(db: AsyncSession = Depends(get_session)):
    return await crud.account.list_all(db)
