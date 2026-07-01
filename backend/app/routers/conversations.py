"""Conversas: contatos com o histórico de mensagens (enviadas e recebidas)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.core.database import get_session

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(account_id: str, db: AsyncSession = Depends(get_session)):
    """Lista contatos (ordenados pela última mensagem) com suas mensagens."""
    contacts = await crud.contact.list_by_account(db, account_id)
    out = []
    for c in contacts:
        messages = await crud.message.list_by_contact(db, c.id)
        out.append(
            {
                "contact": {
                    "id": c.id,
                    "ig_user_id": c.ig_user_id,
                    "username": c.username,
                    "profile_pic": c.profile_pic,
                    "last_message_at": c.last_message_at,
                },
                "messages": [
                    {
                        "id": m.id,
                        "direction": m.direction,
                        "text": m.text,
                        "source": m.source,
                        "created_at": m.created_at,
                    }
                    for m in messages
                ],
            }
        )
    return out
