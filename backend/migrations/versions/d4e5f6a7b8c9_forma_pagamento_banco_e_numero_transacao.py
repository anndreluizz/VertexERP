"""forma de pagamento, banco e numero da transacao em contas a pagar

Revision ID: d4e5f6a7b8c9
Revises: b3d4e5f6a7c8
Create Date: 2026-08-05 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'b3d4e5f6a7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'contas_pagar',
        sa.Column('forma_pagamento', sa.String(length=20), nullable=True),
    )
    op.add_column(
        'contas_pagar',
        sa.Column('banco_pagamento', sa.String(length=60), nullable=True),
    )
    op.add_column(
        'contas_pagar',
        sa.Column('numero_transacao', sa.String(length=80), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('contas_pagar', 'numero_transacao')
    op.drop_column('contas_pagar', 'banco_pagamento')
    op.drop_column('contas_pagar', 'forma_pagamento')
