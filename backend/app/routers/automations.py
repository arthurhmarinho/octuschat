"""CRUD de automações (regras de comentário → mensagem)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import logging

from app import crud
from app.core.database import get_session
from app.schemas.automation import AutomationCreate, AutomationRead, AutomationUpdate
from app.services import instagram_api, token_service

logger = logging.getLogger("inboxpilot.automations")

router = APIRouter(prefix="/automations", tags=["automations"])


@router.get("", response_model=list[AutomationRead])
async def list_automations(
    account_id: str, db: AsyncSession = Depends(get_session)
):
    return await crud.automation.list_by_account(db, account_id)


@router.post("", response_model=AutomationRead, status_code=201)
async def create_automation(
    data: AutomationCreate, db: AsyncSession = Depends(get_session)
):
    account = await crud.account.get(db, data.account_id)
    if account is None:
        raise HTTPException(404, "Conta do Instagram não conectada")
    automation = await crud.automation.create(db, data)

    # "Próxima publicação": snapshot das mídias atuais (baseline) para depois
    # detectar o 1º post novo e vincular a automação a ele.
    if data.bind_next and not data.post_id:
        try:
            account = await token_service.ensure_fresh(db, account)
            media = await instagram_api.list_media(
                account.ig_user_id, account.access_token, limit=50
            )
            automation.baseline_media_ids = [m["id"] for m in media if m.get("id")]
            await db.commit()
            await db.refresh(automation)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha no baseline de 'próxima publicação': %s", exc)
    return automation


@router.get("/{automation_id}", response_model=AutomationRead)
async def get_automation(
    automation_id: int, db: AsyncSession = Depends(get_session)
):
    automation = await crud.automation.get(db, automation_id)
    if automation is None:
        raise HTTPException(404, "Automação não encontrada")
    return automation


@router.patch("/{automation_id}", response_model=AutomationRead)
async def update_automation(
    automation_id: int,
    data: AutomationUpdate,
    db: AsyncSession = Depends(get_session),
):
    automation = await crud.automation.get(db, automation_id)
    if automation is None:
        raise HTTPException(404, "Automação não encontrada")
    return await crud.automation.update(db, automation, data)


@router.delete("/{automation_id}", status_code=204)
async def delete_automation(
    automation_id: int, db: AsyncSession = Depends(get_session)
):
    automation = await crud.automation.get(db, automation_id)
    if automation is None:
        raise HTTPException(404, "Automação não encontrada")
    await crud.automation.delete(db, automation)
