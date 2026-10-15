"""dinheiro guardado (cofre + banco) informado pelo dono

O sistema nao registra pra onde vai o dinheiro quando o caixa fecha;
o dono informa o total guardado e a previsao de 30 dias usa esse valor.

Revision ID: f2a4c6e8d0b1
Revises: e1f3a5c7b9d2
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'f2a4c6e8d0b1'
down_revision: Union[str, Sequence[str], None] = 'e1f3a5c7b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('configuracoes', sa.Column('dinheiro_guardado', sa.Numeric(12, 2), nullable=True))
    op.add_column('configuracoes', sa.Column('dinheiro_guardado_em', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('configuracoes', 'dinheiro_guardado_em')
    op.drop_column('configuracoes', 'dinheiro_guardado')
