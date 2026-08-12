"""adiciona impressao_comprovante em configuracoes

Revision ID: cd66fd47e0fd
Revises: cfe39d695463
Create Date: 2026-07-20 16:27:35.673474

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd66fd47e0fd'
down_revision: Union[str, Sequence[str], None] = 'cfe39d695463'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "configuracoes",
        sa.Column(
            "impressao_comprovante",
            sa.String(length=20),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("configuracoes", "impressao_comprovante")
