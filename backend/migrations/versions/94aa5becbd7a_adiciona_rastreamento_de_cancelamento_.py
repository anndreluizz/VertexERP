"""adiciona rastreamento de cancelamento em vendas

Revision ID: 94aa5becbd7a
Revises: d7c446e70e83
Create Date: 2026-08-13 15:23:00.138097

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '94aa5becbd7a'
down_revision: Union[str, Sequence[str], None] = 'd7c446e70e83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        'vendas',
        sa.Column('cancelado_em', sa.DateTime(), nullable=True),
    )
    op.add_column(
        'vendas',
        sa.Column('cancelado_por_id', sa.Integer(), nullable=True),
    )
    op.add_column(
        'vendas',
        sa.Column(
            'motivo_cancelamento', sa.String(length=255), nullable=True
        ),
    )
    op.create_foreign_key(
        op.f('vendas_cancelado_por_id_fkey'),
        'vendas', 'users', ['cancelado_por_id'], ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_constraint(
        op.f('vendas_cancelado_por_id_fkey'),
        'vendas', type_='foreignkey',
    )
    op.drop_column('vendas', 'motivo_cancelamento')
    op.drop_column('vendas', 'cancelado_por_id')
    op.drop_column('vendas', 'cancelado_em')
