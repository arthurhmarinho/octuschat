"""Conta do Instagram conectada via OAuth da Meta."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
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
    # Token da Meta CIFRADO (Fernet). Nunca leia direto: use
    # token_service.read_token()/get_valid_token().
    access_token_enc: Mapped[str] = mapped_column(String, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Dono da conta (usuário do painel). NULL = conta antiga ainda sem dono;
    # `scripts.create_user --claim-orphans` passa essas contas para um admin.
    owner_user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    # Marcada quando a Meta recusa o token (código 190). Limpa ao reconectar ou
    # renovar. A UI usa para pedir "Reconectar".
    token_invalid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
