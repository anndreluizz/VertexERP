"""catalogo unico entre lojas

Produto exclusivo de uma loja vira global (estoque continua por loja em
estoque_lojas). Fica exclusivo so' quem tem codigo/codigo de barras
repetido com um produto global ou mais antigo -- senao a mesma loja
veria dois produtos com o mesmo codigo.

Revision ID: c8d2e4f6a1b3
Revises: b5e1c0a7d913
Create Date: 2026-10-12

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c8d2e4f6a1b3'
down_revision: Union[str, Sequence[str], None] = 'b5e1c0a7d913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        UPDATE produtos p SET loja_id = NULL
        WHERE p.loja_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM produtos o
            WHERE o.id <> p.id
              AND (o.id < p.id OR o.loja_id IS NULL)
              AND (o.codigo = p.codigo
                   OR (p.codigo_barras IS NOT NULL
                       AND o.codigo_barras = p.codigo_barras))
          )
    """)


def downgrade() -> None:
    # so' dados: nao da pra saber de qual loja cada produto era
    pass
