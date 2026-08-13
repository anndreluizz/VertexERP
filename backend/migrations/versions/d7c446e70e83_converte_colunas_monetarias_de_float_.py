"""converte colunas monetarias de Float para Numeric(12,2)

Revision ID: d7c446e70e83
Revises: d88cbc3f1403
Create Date: 2026-08-12 11:08:29.570876

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7c446e70e83'
down_revision: Union[str, Sequence[str], None] = 'd88cbc3f1403'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


"""Colunas de dinheiro migrando de Float (double precision) pra
Numeric(12,2) — Float acumula erro de arredondamento em ponto
flutuante binario (ex.: 0.1 + 0.2 != 0.3), o que nao e aceitavel pra
valor financeiro. Numeric(12,2) guarda o valor exato, ate
R$ 999.999.999,99.

O "USING coluna::numeric(12,2)" converte os dados ja existentes na
hora do ALTER — os valores atuais (que ja sao centavos "limpos", so
o TIPO de armazenamento que era impreciso) sao preservados."""

COLUNAS = [
    ("caixa", "saldo_inicial"),
    ("caixa", "saldo_final"),
    ("caixa", "valor_contado"),
    ("clientes", "limite_credito"),
    ("compras", "valor_total"),
    ("contas_pagar", "valor"),
    ("contas_receber", "valor"),
    ("itens_compra", "valor_unitario"),
    ("itens_compra", "subtotal"),
    ("itens_venda", "valor_unitario"),
    ("itens_venda", "subtotal"),
    ("movimentos_caixa", "valor"),
    ("movimentos_fiado", "valor"),
    ("produtos", "preco_custo"),
    ("produtos", "preco_venda"),
    ("vendas", "valor_total"),
    ("vendas", "desconto"),
    ("vendas", "valor_forma_2"),
]


def upgrade() -> None:
    """Upgrade schema."""

    for tabela, coluna in COLUNAS:
        op.alter_column(
            tabela,
            coluna,
            existing_type=sa.Float(),
            type_=sa.Numeric(12, 2),
            postgresql_using=f"{coluna}::numeric(12,2)",
        )


def downgrade() -> None:
    """Downgrade schema."""

    for tabela, coluna in COLUNAS:
        op.alter_column(
            tabela,
            coluna,
            existing_type=sa.Numeric(12, 2),
            type_=sa.Float(),
            postgresql_using=f"{coluna}::double precision",
        )
