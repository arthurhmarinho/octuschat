"""Entrypoint do backend FastAPI do InboxPilot."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import crypto
from app.core.config import settings
from app.routers import (
    automations,
    contacts,
    conversations,
    health,
    instagram,
    webhooks,
)

logging.basicConfig(level=logging.INFO)
# O httpx loga cada URL em INFO — com query strings que podem ter segredos
# (ex.: troca/renovação de token). Só avisos e erros.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("inboxpilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # O schema é gerido pelo Alembic (`alembic upgrade head`), não no startup.
    if not settings.api_secret:
        logger.warning("API_SECRET vazio — todas as rotas protegidas vão responder 401.")
    if not crypto.is_configured():
        logger.error(
            "TOKEN_ENCRYPTION_KEYS ausente ou inválida — não dá para ler os tokens da Meta."
        )
    yield


app = FastAPI(
    title=settings.app_name,
    description="Automação de DMs do Instagram via comentários e palavras-chave.",
    version="0.1.0",
    lifespan=lifespan,
    # Em produção não expomos a documentação/esquema da API.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
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
app.include_router(contacts.router)
app.include_router(conversations.router)
