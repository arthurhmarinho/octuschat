"""Regra de automação: 'quando X acontece, envie a mensagem Y'."""

import enum
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TriggerType(str, enum.Enum):
    COMMENT_ANY = "comment_any"          # qualquer comentário no post
    COMMENT_KEYWORD = "comment_keyword"  # comentário contendo palavra-chave
    DM_KEYWORD = "dm_keyword"            # DM recebida contendo palavra-chave
    DM_ANY = "dm_any"                    # qualquer DM (resposta padrão / fallback)


# Conjuntos auxiliares para saber o "canal" do gatilho.
COMMENT_TRIGGERS = {TriggerType.COMMENT_ANY, TriggerType.COMMENT_KEYWORD}
DM_TRIGGERS = {TriggerType.DM_KEYWORD, TriggerType.DM_ANY}
KEYWORD_TRIGGERS = {TriggerType.COMMENT_KEYWORD, TriggerType.DM_KEYWORD}


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
    # palavras que, se presentes no comentário, IMPEDEM o disparo (separadas por vírgula)
    exclude_keywords: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # None = aplica a todos os posts da conta (a menos que bind_next=True)
    post_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # "próxima publicação": enquanto post_id é None, aguarda o 1º post novo
    # (id fora de baseline_media_ids) para se vincular a ele.
    bind_next: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    baseline_media_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    reply_message: Mapped[str] = mapped_column(Text, nullable=False)
    # resposta PÚBLICA opcional no próprio comentário (ex.: "Enviei no seu direct 🚀")
    public_reply: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    # Link opcional anexado à DM (compat; substituído por buttons).
    link_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    link_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Botões de link na DM (até 3): lista de {"label": str, "url": str}.
    buttons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
