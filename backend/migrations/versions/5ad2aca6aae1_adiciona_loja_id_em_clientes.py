"""adiciona loja_id em clientes

Revision ID: 5ad2aca6aae1
Revises: 559952ab5045
Create Date: 2026-09-16 13:20:28.074094

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ad2aca6aae1'
down_revision: Union[str, Sequence[str], None] = '559952ab5045'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # so' clientes.loja_id -- o autogenerate tambem detectou drift
    # nao relacionado em produtos/refresh_tokens (trabalho em
    # andamento ja existente antes desta migracao), deixado de fora
    # de proposito pra nao misturar com essa mudanca.
    op.add_column('clientes', sa.Column('loja_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_clientes_loja_id'), 'clientes', ['loja_id'], unique=False)
    op.create_foreign_key(None, 'clientes', 'lojas', ['loja_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(None, 'clientes', type_='foreignkey')
    op.drop_index(op.f('ix_clientes_loja_id'), table_name='clientes')
    op.drop_column('clientes', 'loja_id')
