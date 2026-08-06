"""documento anexado (boleto/nota) em contas a pagar

Revision ID: a7c8d9e0f1b2
Revises: f1a2b3c4d5e6
Create Date: 2026-08-05 09:15:51.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c8d9e0f1b2'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'contas_pagar',
        sa.Column('documento', sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        'contas_pagar',
        sa.Column('documento_nome', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'contas_pagar',
        sa.Column('documento_tipo', sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('contas_pagar', 'documento_tipo')
    op.drop_column('contas_pagar', 'documento_nome')
    op.drop_column('contas_pagar', 'documento')
