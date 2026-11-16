"""Evento cru recebido do webhook da Meta, enfileirado para processamento.

O endpoint do webhook só grava aqui e responde 200 na hora; o worker
(`app/workers/webhook_worker.py`) consome a fila com
`SELECT … FOR UPDATE SKIP LOCKED`.

Ciclo de vida: pending → processing → done
                          └→ pending (retry, com backoff via available_at)
                          └→ failed  (esgotou as tentativas)
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

PENDING = "pending"
PROCESSING = "processing"
DONE = "done"
FAILED = "failed"


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        # Consulta do worker: pendentes já liberados, em ordem de chegada.
        Index("ix_webhook_events_status_available", "status", "available_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Chave de deduplicação (a Meta reenvia eventos): comment:<id>, mid:<mid>
    # ou sha256 do item quando não há id.
    dedupe_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # entry.id do webhook (ig_id). Base para o rate limiter por conta.
    account_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # comment | message
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=PENDING, server_default=PENDING
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Só é processado a partir deste instante (backoff de retry / rate limit).
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
