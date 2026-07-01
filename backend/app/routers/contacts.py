"""Lista de contatos (pessoas com quem a conta interagiu)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.database import get_session

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("")
async def list_contacts(account_id: str, db: AsyncSession = Depends(get_session)):
    contacts = await crud.contact.list_by_account(db, account_id)
    return [
        {
            "id": c.id,
            "ig_user_id": c.ig_user_id,
            "username": c.username,
            "profile_pic": c.profile_pic,
            "first_seen": c.first_seen,
            "last_message_at": c.last_message_at,
        }
        for c in contacts
    ]
