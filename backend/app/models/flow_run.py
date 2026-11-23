"""Execução de um flow para um contato (estado entre mensagens).

Um flow pode esperar: o toque numa resposta rápida, o texto de uma Pergunta ou
um atraso. Enquanto espera, o estado fica aqui. A execução guarda uma CÓPIA do
grafo do momento em que começou, então editar a automação não quebra quem
está no meio dela.

Ciclo de vida:

    running ──► waiting ──► running ──► … ──► completed
       │            │
       │            └─► expired   (janela de 24h fechada / prazo vencido)
       ├─► failed                 (erro no envio)
       └─► cancelled

`running` e `waiting` são os estados ATIVOS: só pode haver uma execução ativa
por (automação, contato) (índice único parcial).
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

RUNNING = "running"
WAITING = "waiting"
COMPLETED = "completed"
EXPIRED = "expired"
FAILED = "failed"
CANCELLED = "cancelled"

ACTIVE = (RUNNING, WAITING)
FINISHED = (COMPLETED, EXPIRED, FAILED, CANCELLED)

WAIT_REPLY = "reply"
WAIT_TIMER = "timer"


class FlowRun(Base):
    __tablename__ = "flow_runs"
    __table_args__ = (
        # Uma execução ativa por automação e contato.
        Index(
            "uq_flow_runs_active",
            "automation_id",
            "contact_id",
            unique=True,
            postgresql_where=text("status IN ('running','waiting')"),
        ),
        # Consulta do worker: quem está esperando e já venceu.
        Index("ix_flow_runs_status_resume", "status", "resume_at"),
        # Achar a execução que espera a resposta deste contato.
        Index("ix_flow_runs_account_contact_status", "account_id", "contact_id", "status"),
        Index("ix_flow_runs_automation_created", "automation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    automation_id: Mapped[int] = mapped_column(
        ForeignKey("automations.id", ondelete="CASCADE"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(String(64), nullable=False)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    # Cópia do grafo no início da execução.
    graph: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=RUNNING, server_default=RUNNING
    )
    current_node_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # `reply` (espera o contato) ou `timer` (atraso); nulo quando não espera.
    waiting_for: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # {"text", "is_new_contact", "username", "vars": {}}
    context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    # timer: fim do atraso. reply: prazo do timeout.
    resume_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # id do comentário ou mid da DM que iniciou a execução.
    trigger_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
