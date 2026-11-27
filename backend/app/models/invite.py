"""Convite por link: cadastro de pessoa nova ou redefinição de senha.

O token vai no link e só é mostrado na criação; no banco fica o sha256 dele.
Um convite está VÁLIDO enquanto não foi usado, não foi cancelado e não venceu.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

SIGNUP = "signup"
RESET = "reset"


class UserInvite(Base):
    __tablename__ = "user_invites"
    __table_args__ = (
        CheckConstraint("purpose in ('signup','reset')", name="ck_user_invites_purpose"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Sempre em minúsculas.
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # @ do Instagram convidado, sem "@" e em minúsculas.
    ig_username: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # reset: o usuário-alvo. signup: preenchido quando o convite é usado.
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    # Quando o dono marcou que adicionou o @ como Testador do Instagram na Meta.
    meta_tester_added_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
