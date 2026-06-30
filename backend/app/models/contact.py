"""Contato: uma pessoa do Instagram com quem a conta interagiu."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Contact(Base):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint("account_id", "ig_user_id", name="uq_contact_account_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("instagram_accounts.ig_user_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # id do contato escopado ao app (IGSID) — vem do comentário/DM.
    ig_user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
