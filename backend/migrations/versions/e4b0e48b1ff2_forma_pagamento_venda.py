"""forma pagamento venda

Revision ID: e4b0e48b1ff2
Revises: 2276322528e7
Create Date: 2026-07-06 18:37:39.816033

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4b0e48b1ff2"
down_revision: Union[str, Sequence[str], None] = "2276322528e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1 - Adiciona a coluna permitindo NULL
    op.add_column(
        "vendas",
        sa.Column(
            "forma_pagamento",
            sa.String(length=20),
            nullable=True,
        ),
    )

    # 2 - Adiciona a data de vencimento
    op.add_column(
        "vendas",
        sa.Column(
            "data_vencimento",
            sa.DateTime(),
            nullable=True,
        ),
    )

    # 3 - Atualiza todas as vendas antigas
    op.execute(
        """
        UPDATE vendas
        SET forma_pagamento = 'AVISTA'
        WHERE forma_pagamento IS NULL
        """
    )

    # 4 - Agora torna obrigatório
    op.alter_column(
        "vendas",
        "forma_pagamento",
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("vendas", "data_vencimento")
    op.drop_column("vendas", "forma_pagamento")