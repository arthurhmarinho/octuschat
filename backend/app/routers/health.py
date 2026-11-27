"""Healthcheck — usado pelo frontend e pelo monitor do Railway/Render."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


# HEAD: alguns serviços de ping usam. Não toca no banco: serve só para o
# monitor e para manter a instância acordada.
@router.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok", "service": "octus-chat-backend"}
