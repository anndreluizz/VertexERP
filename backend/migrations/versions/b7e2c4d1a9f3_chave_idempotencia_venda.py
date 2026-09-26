"""chave de idempotencia da venda

Revision ID: b7e2c4d1a9f3
Revises: d4e7a1c9b2f0
Create Date: 2026-09-26 12:00:00

Coluna nova, anulavel e unica: vendas existentes ficam com NULL (o
Postgres aceita varios NULL num indice unico), entao a migracao nao
tem como falhar por causa de dado ja existente no banco da loja.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e2c4d1a9f3'
down_revision: Union[str, Sequence[str], None] = 'd4e7a1c9b2f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'vendas',
        sa.Column('chave_idempotencia', sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        'vendas_chave_idempotencia_key', 'vendas', ['chave_idempotencia']
    )


def downgrade() -> None:
    op.drop_constraint('vendas_chave_idempotencia_key', 'vendas', type_='unique')
    op.drop_column('vendas', 'chave_idempotencia')
