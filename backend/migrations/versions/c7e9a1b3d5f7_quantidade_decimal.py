"""quantidade/estoque decimais (venda por peso)

Produto em KG/L vende 0,350 kg: toda quantidade e estoque passam de
inteiro pra Numeric(12, 3). Valores existentes viram 5.000 etc.

Revision ID: c7e9a1b3d5f7
Revises: b4d6f8a0c2e5
Create Date: 2026-10-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'c7e9a1b3d5f7'
down_revision: Union[str, Sequence[str], None] = 'b4d6f8a0c2e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUNAS = [
    ('produtos', 'estoque'),
    ('produtos', 'estoque_minimo'),
    ('estoque_lojas', 'quantidade'),
    ('estoque_lojas', 'estoque_minimo'),
    ('itens_venda', 'quantidade'),
    ('itens_compra', 'quantidade'),
    ('itens_devolucao', 'quantidade'),
    ('kit_itens', 'quantidade'),
    ('movimentos_estoque', 'quantidade'),
    ('transferencias_estoque', 'quantidade'),
    ('itens_contagem_estoque', 'quantidade_sistema'),
    ('itens_contagem_estoque', 'quantidade_contada'),
]


def upgrade() -> None:
    for tabela, coluna in COLUNAS:
        op.alter_column(tabela, coluna, type_=sa.Numeric(12, 3),
                        existing_type=sa.Integer())


def downgrade() -> None:
    # arredonda o que tiver fracao (vendas por peso perdem a precisao)
    for tabela, coluna in COLUNAS:
        op.alter_column(tabela, coluna, type_=sa.Integer(),
                        existing_type=sa.Numeric(12, 3),
                        postgresql_using=f'round({coluna})::integer')
