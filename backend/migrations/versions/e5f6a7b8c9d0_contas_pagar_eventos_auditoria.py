"""contas_pagar_eventos: linha do tempo de auditoria por despesa

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-05 17:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'contas_pagar_eventos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conta_pagar_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=40), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('dispositivo', sa.String(length=60), nullable=True),
        sa.Column('detalhes', sa.String(length=255), nullable=True),
        sa.Column('data', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['conta_pagar_id'], ['contas_pagar.id'], ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(['usuario_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_contas_pagar_eventos_id'),
        'contas_pagar_eventos', ['id'], unique=False,
    )
    op.create_index(
        op.f('ix_contas_pagar_eventos_conta_pagar_id'),
        'contas_pagar_eventos', ['conta_pagar_id'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f('ix_contas_pagar_eventos_conta_pagar_id'),
        table_name='contas_pagar_eventos',
    )
    op.drop_index(
        op.f('ix_contas_pagar_eventos_id'), table_name='contas_pagar_eventos',
    )
    op.drop_table('contas_pagar_eventos')
