"""CRUD de automações (regras de comentário → mensagem)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import logging

from app import crud
from app.core.auth import current_user
from app.core.database import get_session
from app.core.ownership import owned_account
from app.models.automation import Automation
from app.models.user import User
from app.schemas.automation import (
    AutomationCreate,
    AutomationRead,
    AutomationUpdate,
    check_start_for_trigger,
)
from app.services import instagram_api, token_service

logger = logging.getLogger("inboxpilot.automations")

router = APIRouter(prefix="/automations", tags=["automations"])


async def _owned_automation(
    automation_id: int, user: User, db: AsyncSession
) -> Automation:
    """A automação só se a conta dela for do usuário; senão 404."""
    automation = await crud.automation.get(db, automation_id)
    if automation is None or await crud.account.get_owned(
        db, user.id, automation.account_id
    ) is None:
        raise HTTPException(404, "Automação não encontrada")
    return automation


@router.get("", response_model=list[AutomationRead])
async def list_automations(
    account_id: str,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    await owned_account(account_id, user, db)
    return await crud.automation.list_by_account(db, account_id)


@router.post("", response_model=AutomationRead, status_code=201)
async def create_automation(
    data: AutomationCreate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    account = await owned_account(data.account_id, user, db)
    automation = await crud.automation.create(db, data)

    # "Próxima publicação": snapshot das mídias atuais (baseline) para depois
    # detectar o 1º post novo e vincular a automação a ele.
    if data.bind_next and not data.post_id:
        try:
            token = await token_service.get_valid_token(db, account)
            media = await instagram_api.list_media(account.ig_user_id, token, limit=50)
            automation.baseline_media_ids = [m["id"] for m in media if m.get("id")]
            await db.commit()
            await db.refresh(automation)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Falha no baseline de 'próxima publicação': %s", exc)
    return automation


@router.get("/{automation_id}", response_model=AutomationRead)
async def get_automation(
    automation_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    return await _owned_automation(automation_id, user, db)


@router.patch("/{automation_id}", response_model=AutomationRead)
async def update_automation(
    automation_id: int,
    data: AutomationUpdate,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    automation = await _owned_automation(automation_id, user, db)
    # Gatilho e grafo se validam juntos: um PATCH só com o gatilho (ou só com o
    # grafo) não pode deixar a combinação inválida.
    if data.graph is not None or data.trigger is not None:
        graph = data.graph.model_dump() if data.graph is not None else automation.graph
        start = next(
            (n for n in (graph or {}).get("nodes", []) if n.get("id") == (graph or {}).get("start")),
            {},
        )
        try:
            check_start_for_trigger(start.get("type") or "message", data.trigger or automation.trigger)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    return await crud.automation.update(db, automation, data)


@router.delete("/{automation_id}", status_code=204)
async def delete_automation(
    automation_id: int,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_session),
):
    automation = await _owned_automation(automation_id, user, db)
    await crud.automation.delete(db, automation)
