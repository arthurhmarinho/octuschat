"""Regra de automação: 'quando X acontece, envie a mensagem Y'."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TriggerType(str, enum.Enum):
    COMMENT_ANY = "comment_any"          # qualquer comentário no post
    COMMENT_KEYWORD = "comment_keyword"  # comentário contendo palavra-chave


class Automation(Base):
    __tablename__ = "automations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(
        ForeignKey("instagram_accounts.ig_user_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    trigger: Mapped[TriggerType] = mapped_column(
        Enum(TriggerType, name="trigger_type"), nullable=False
    )
    # usado quando trigger == COMMENT_KEYWORD
    keyword: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # None = aplica a todos os posts da conta
    post_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    reply_message: Mapped[str] = mapped_column(Text, nullable=False)
    # Link opcional anexado à DM (estilo ManyChat: texto + botão com URL).
    link_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    link_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
