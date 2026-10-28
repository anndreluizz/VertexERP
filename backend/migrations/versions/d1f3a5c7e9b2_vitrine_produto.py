"""vitrine virtual: produto publicado/destaque no site da loja

Revision ID: d1f3a5c7e9b2
Revises: b4d6f8a0c2e5
Create Date: 2026-10-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'd1f3a5c7e9b2'
down_revision: Union[str, Sequence[str], None] = 'b4d6f8a0c2e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('produtos', sa.Column('vitrine_publicar', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('produtos', sa.Column('vitrine_destaque', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('produtos', 'vitrine_destaque')
    op.drop_column('produtos', 'vitrine_publicar')
