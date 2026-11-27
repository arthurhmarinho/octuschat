"""Convites por link (`user_invites`) — só cria tabela, sem tocar em dados.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-27

Cadastro por convite e redefinição de senha. O token fica só como hash.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_invites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('purpose', sa.String(length=10), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('ig_username', sa.String(length=30), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('meta_tester_added_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("purpose in ('signup','reset')", name='ck_user_invites_purpose'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token_hash'),
    )
    op.create_index('ix_user_invites_user_id', 'user_invites', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_user_invites_user_id', table_name='user_invites')
    op.drop_table('user_invites')
