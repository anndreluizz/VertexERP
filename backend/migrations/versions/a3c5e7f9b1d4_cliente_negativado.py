"""cliente negativado

Cliente negativado nao compra nada (nem a vista); a divida dele e'
baixada como perda (movimento de fiado tipo PERDA) e sai do fiado em
aberto, mas continua no historico.

Revision ID: a3c5e7f9b1d4
Revises: f2a4c6e8d0b1
Create Date: 2026-10-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'a3c5e7f9b1d4'
down_revision: Union[str, Sequence[str], None] = 'f2a4c6e8d0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clientes', sa.Column('negativado', sa.Boolean(), nullable=False,
                                        server_default=sa.false()))
    op.add_column('clientes', sa.Column('negativado_em', sa.DateTime(), nullable=True))
    op.add_column('clientes', sa.Column('negativado_motivo', sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column('clientes', 'negativado_motivo')
    op.drop_column('clientes', 'negativado_em')
    op.drop_column('clientes', 'negativado')
