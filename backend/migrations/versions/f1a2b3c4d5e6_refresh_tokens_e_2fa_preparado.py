"""refresh tokens (sessoes/logout remoto) e coluna 2fa preparada

Revision ID: f1a2b3c4d5e6
Revises: c3f9a281d6e4
Create Date: 2026-08-05 08:38:26.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'c3f9a281d6e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('dispositivo', sa.String(length=120), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('expira_em', sa.DateTime(), nullable=False),
        sa.Column('ultimo_uso_em', sa.DateTime(), nullable=False),
        sa.Column(
            'revogado',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.ForeignKeyConstraint(['usuario_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index(
        op.f('ix_refresh_tokens_id'), 'refresh_tokens', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_refresh_tokens_token'),
        'refresh_tokens',
        ['token'],
        unique=True,
    )

    op.add_column(
        'users',
        sa.Column(
            'dois_fatores_ativo',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'dois_fatores_ativo')

    op.drop_index(op.f('ix_refresh_tokens_token'), table_name='refresh_tokens')
    op.drop_index(op.f('ix_refresh_tokens_id'), table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
