"""adiciona venda_id em movimentos_caixa

Revision ID: d9ee2d6468be
Revises: cd66fd47e0fd
Create Date: 2026-07-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9ee2d6468be'
down_revision: Union[str, Sequence[str], None] = 'cd66fd47e0fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "movimentos_caixa",
        sa.Column("venda_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_movimentos_caixa_venda_id_vendas",
        "movimentos_caixa",
        "vendas",
        ["venda_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_movimentos_caixa_venda_id_vendas",
        "movimentos_caixa",
        type_="foreignkey",
    )
    op.drop_column("movimentos_caixa", "venda_id")
