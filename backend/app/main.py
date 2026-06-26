"""Entrypoint do backend FastAPI do InboxPilot."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db
from app.routers import automations, health, instagram, webhooks

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Em dev/demo criamos as tabelas no startup. Em produção, use Alembic.
    await init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Automação de DMs do Instagram via comentários e palavras-chave.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(webhooks.router)
app.include_router(instagram.router)
app.include_router(automations.router)
