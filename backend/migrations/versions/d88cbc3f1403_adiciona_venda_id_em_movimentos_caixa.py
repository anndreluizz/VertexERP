"""adiciona venda_id em movimentos_caixa

Revision ID: d88cbc3f1403
Revises: a1b2c3d4e5f7
Create Date: 2026-08-12 10:15:08.980663

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd88cbc3f1403'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'movimentos_caixa',
        sa.Column('venda_id', sa.Integer(), nullable=True),
    )
    op.create_index(
        op.f('ix_movimentos_caixa_venda_id'),
        'movimentos_caixa', ['venda_id'], unique=False,
    )
    op.create_foreign_key(
        op.f('movimentos_caixa_venda_id_fkey'),
        'movimentos_caixa', 'vendas', ['venda_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f('movimentos_caixa_venda_id_fkey'),
        'movimentos_caixa', type_='foreignkey',
    )
    op.drop_index(
        op.f('ix_movimentos_caixa_venda_id'),
        table_name='movimentos_caixa',
    )
    op.drop_column('movimentos_caixa', 'venda_id')
