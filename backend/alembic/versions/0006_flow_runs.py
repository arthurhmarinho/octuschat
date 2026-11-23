"""Execuções de flow (`flow_runs`) — só cria tabela, sem tocar em dados.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-23

Estado de um flow que espera (resposta rápida, pergunta, atraso). Guarda uma
cópia do grafo, para editar a automação não quebrar quem está no meio dela.
Índice único parcial: uma execução ativa por (automação, contato).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'flow_runs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('automation_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.String(length=64), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('graph', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=16), server_default='running', nullable=False),
        sa.Column('current_node_id', sa.String(length=64), nullable=True),
        sa.Column('waiting_for', sa.String(length=8), nullable=True),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('resume_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('trigger_ref', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['automation_id'], ['automations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'uq_flow_runs_active', 'flow_runs', ['automation_id', 'contact_id'],
        unique=True, postgresql_where=sa.text("status IN ('running','waiting')"),
    )
    op.create_index('ix_flow_runs_status_resume', 'flow_runs', ['status', 'resume_at'], unique=False)
    op.create_index('ix_flow_runs_account_contact_status', 'flow_runs', ['account_id', 'contact_id', 'status'], unique=False)
    op.create_index('ix_flow_runs_automation_created', 'flow_runs', ['automation_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_flow_runs_automation_created', table_name='flow_runs')
    op.drop_index('ix_flow_runs_account_contact_status', table_name='flow_runs')
    op.drop_index('ix_flow_runs_status_resume', table_name='flow_runs')
    op.drop_index('uq_flow_runs_active', table_name='flow_runs', postgresql_where=sa.text("status IN ('running','waiting')"))
    op.drop_table('flow_runs')
