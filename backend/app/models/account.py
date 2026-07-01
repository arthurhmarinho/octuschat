"""Conta do Instagram conectada via OAuth da Meta."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class InstagramAccount(Base):
    __tablename__ = "instagram_accounts"

    # ig_user_id é o identificador usado nas chamadas da Graph API (user_id do OAuth).
    ig_user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # ig_id é o identificador que a Meta usa no webhook (entry.id) — costuma
    # ser DIFERENTE do ig_user_id. Guardamos para casar os eventos recebidos.
    ig_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
