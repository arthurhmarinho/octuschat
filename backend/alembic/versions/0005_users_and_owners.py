"""Usuários do painel + dono das contas do Instagram + marca de token inválido.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-23

- `users`: login por e-mail e senha (scrypt). A migração NÃO cria usuário
  (não há como saber a senha): use `python -m scripts.create_user`.
- `instagram_accounts.owner_user_id`: dono da conta. As contas existentes ficam
  com NULL até `create_user --claim-orphans`.
- `instagram_accounts.token_invalid_at`: marcada quando a Meta responde 190.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('is_admin', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('must_change_password', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.add_column('instagram_accounts', sa.Column('owner_user_id', sa.Integer(), nullable=True))
    op.add_column('instagram_accounts', sa.Column('token_invalid_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_instagram_accounts_owner_user_id'), 'instagram_accounts', ['owner_user_id'], unique=False)
    op.create_foreign_key(
        'fk_instagram_accounts_owner_user_id', 'instagram_accounts', 'users',
        ['owner_user_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_instagram_accounts_owner_user_id', 'instagram_accounts', type_='foreignkey')
    op.drop_index(op.f('ix_instagram_accounts_owner_user_id'), table_name='instagram_accounts')
    op.drop_column('instagram_accounts', 'token_invalid_at')
    op.drop_column('instagram_accounts', 'owner_user_id')
    op.drop_table('users')
