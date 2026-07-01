"""CRUD de automações (regras de comentário → mensagem)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.database import get_session
from app.schemas.automation import AutomationCreate, AutomationRead, AutomationUpdate

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
    return await crud.automation.create(db, data)


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
