"""cria contas receber

Revision ID: 2276322528e7
Revises: 237dbb285d34
Create Date: 2026-07-06 18:26:55.134598

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2276322528e7"
down_revision: Union[str, Sequence[str], None] = "237dbb285d34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "contas_receber",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "cliente_id",
            sa.Integer(),
            sa.ForeignKey("clientes.id"),
            nullable=False,
        ),

        sa.Column(
            "venda_id",
            sa.Integer(),
            sa.ForeignKey("vendas.id"),
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
            "data_recebimento",
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

    op.drop_table("contas_receber")