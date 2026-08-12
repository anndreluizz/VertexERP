"""contas pagar

Revision ID: fe22824d45f9
Revises: e4b0e48b1ff2
Create Date: 2026-07-06 19:42:19.158937

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fe22824d45f9"
down_revision: Union[str, Sequence[str], None] = "e4b0e48b1ff2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "contas_pagar",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "fornecedor_id",
            sa.Integer(),
            sa.ForeignKey("fornecedores.id"),
            nullable=False,
        ),

        sa.Column(
            "compra_id",
            sa.Integer(),
            sa.ForeignKey("compras.id"),
            nullable=True,
        ),

        sa.Column(
            "data_emissao",
            sa.DateTime(),
            nullable=False,
        ),

        sa.Column(
            "data_vencimento",
            sa.DateTime(),
            nullable=False,
        ),

        sa.Column(
            "data_pagamento",
            sa.DateTime(),
            nullable=True,
        ),

        sa.Column(
            "valor",
            sa.Float(),
            nullable=False,
        ),

        sa.Column(
            "observacao",
            sa.String(length=255),
            nullable=True,
        ),

        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_table("contas_pagar")