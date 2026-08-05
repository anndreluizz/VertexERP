"""solicitacoes de aprovacao (acoes sensiveis pendentes de admin)

Revision ID: c3f9a281d6e4
Revises: 0b4eea69adc2
Create Date: 2026-08-04 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f9a281d6e4'
down_revision: Union[str, Sequence[str], None] = '0b4eea69adc2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'solicitacoes_aprovacao',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=40), nullable=False),
        sa.Column('referencia_id', sa.Integer(), nullable=False),
        sa.Column('descricao', sa.String(length=255), nullable=False),
        sa.Column(
            'status',
            sa.String(length=20),
            nullable=False,
            server_default='PENDENTE',
        ),
        sa.Column('solicitante_id', sa.Integer(), nullable=False),
        sa.Column('aprovador_id', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('resolvido_em', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['solicitante_id'], ['users.id']),
        sa.ForeignKeyConstraint(['aprovador_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_solicitacoes_aprovacao_id'),
        'solicitacoes_aprovacao',
        ['id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_solicitacoes_aprovacao_id'),
        table_name='solicitacoes_aprovacao',
    )
    op.drop_table('solicitacoes_aprovacao')
