"""movimento fiado guarda o caixa

Recebimento de fiado guarda em qual caixa o dinheiro entrou, pra
correcao/exclusao ajustar esse caixa (se ainda aberto) e nao o de quem
esta corrigindo. Os antigos sao ligados pelo lancamento de caixa gerado
junto (mesmo usuario, valor e forma, ate 10 min de diferenca).

Revision ID: e1f3a5c7b9d2
Revises: c8d2e4f6a1b3
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e1f3a5c7b9d2'
down_revision: Union[str, Sequence[str], None] = 'c8d2e4f6a1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'movimentos_fiado',
        sa.Column('caixa_id', sa.Integer(), sa.ForeignKey('caixa.id'), nullable=True),
    )
    op.create_index('ix_movimentos_fiado_caixa_id', 'movimentos_fiado', ['caixa_id'])
    op.execute("""
        UPDATE movimentos_fiado mf SET caixa_id = (
            SELECT mc.caixa_id FROM movimentos_caixa mc
            WHERE mc.tipo = 'RECEBIMENTO_FIADO'
              AND mc.usuario_id = mf.usuario_id
              AND mc.valor = mf.valor
              AND mc.forma_pagamento = mf.forma_pagamento
              AND left(mc.descricao, 17) = 'Pagamento fiado -'
              AND abs(extract(epoch FROM mc.data - mf.data)) < 600
            ORDER BY abs(extract(epoch FROM mc.data - mf.data))
            LIMIT 1
        )
        WHERE mf.tipo = 'PAGAMENTO' AND mf.forma_pagamento IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_index('ix_movimentos_fiado_caixa_id', 'movimentos_fiado')
    op.drop_column('movimentos_fiado', 'caixa_id')
