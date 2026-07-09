"""Healthcheck — usado pelo frontend e pelo monitor do Railway/Render."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": "octus-chat-backend"}
