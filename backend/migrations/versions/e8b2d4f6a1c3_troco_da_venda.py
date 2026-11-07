"""troco da venda (pra sair no cupom e na 2a via)

Revision ID: e8b2d4f6a1c3
Revises: d1f3a5c7e9b2
Create Date: 2026-11-07

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'e8b2d4f6a1c3'
down_revision: Union[str, Sequence[str], None] = 'd1f3a5c7e9b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vendas', sa.Column('troco', sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('vendas', 'troco')
