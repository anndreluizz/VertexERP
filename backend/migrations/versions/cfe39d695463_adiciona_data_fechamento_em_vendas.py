"""adiciona data_fechamento em vendas

Revision ID: cfe39d695463
Revises: e154ba616fe0
Create Date: 2026-07-20 08:23:26.931057

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cfe39d695463'
down_revision: Union[str, Sequence[str], None] = 'e154ba616fe0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS: essa coluna já foi adicionada manualmente no banco da
    # loja de verdade antes dessa migração existir (ficou fora da cadeia
    # do alembic por engano) — sem essa guarda, rodar upgrade nela de novo
    # quebraria com "column already exists".
    op.execute(
        "ALTER TABLE vendas ADD COLUMN IF NOT EXISTS data_fechamento "
        "TIMESTAMP"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE vendas DROP COLUMN IF EXISTS data_fechamento"
    )
