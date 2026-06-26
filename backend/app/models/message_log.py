"""Registro de mensagens disparadas — auditoria e idempotência.

Evita responder o mesmo comentário duas vezes (a Meta pode reenviar o
webhook) e dá histórico para o dashboard.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MessageLog(Base):
    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    automation_id: Mapped[int | None] = mapped_column(
        ForeignKey("automations.id", ondelete="SET NULL"), nullable=True
    )
    # comment_id é único para garantir idempotência por comentário.
    comment_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    recipient_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # sent | failed
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
