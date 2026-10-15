"""destino do dinheiro no fechamento do caixa

Ao fechar, o operador diz quanto foi pro cofre/banco e quanto os socios
retiraram (o resto fica de troco). Com isso o "dinheiro guardado" da
Inteligencia de Negocios se atualiza sozinho a partir do ultimo valor
informado pelo dono.

Revision ID: b4d6f8a0c2e5
Revises: a3c5e7f9b1d4
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'b4d6f8a0c2e5'
down_revision: Union[str, Sequence[str], None] = 'a3c5e7f9b1d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('caixa', sa.Column('valor_guardado', sa.Numeric(12, 2), nullable=True))
    op.add_column('caixa', sa.Column('valor_retirado', sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('caixa', 'valor_retirado')
    op.drop_column('caixa', 'valor_guardado')
