"""comprovante de pagamento em contas a pagar

Revision ID: b3d4e5f6a7c8
Revises: a7c8d9e0f1b2
Create Date: 2026-08-05 12:34:30.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3d4e5f6a7c8'
down_revision: Union[str, Sequence[str], None] = 'a7c8d9e0f1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'contas_pagar',
        sa.Column('comprovante_pagamento', sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        'contas_pagar',
        sa.Column(
            'comprovante_pagamento_nome',
            sa.String(length=255),
            nullable=True,
        ),
    )
    op.add_column(
        'contas_pagar',
        sa.Column(
            'comprovante_pagamento_tipo',
            sa.String(length=100),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('contas_pagar', 'comprovante_pagamento_tipo')
    op.drop_column('contas_pagar', 'comprovante_pagamento_nome')
    op.drop_column('contas_pagar', 'comprovante_pagamento')
