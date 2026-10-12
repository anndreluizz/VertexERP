"""contas a pagar: pix (chave ou copia e cola)

Revision ID: b5e1c0a7d913
Revises: 38c9dfe20eaf
Create Date: 2026-10-12 08:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e1c0a7d913'
down_revision: Union[str, Sequence[str], None] = '38c9dfe20eaf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('contas_pagar', sa.Column('pix', sa.String(length=512), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('contas_pagar', 'pix')
