"""fornecedor margem padrao e compra cancelado em

Revision ID: 5350f91ba853
Revises: c3d7714b9466
Create Date: 2026-09-19 16:05:55.743019

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5350f91ba853'
down_revision: Union[str, Sequence[str], None] = 'c3d7714b9466'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.add_column(
        'compras', sa.Column('cancelado_em', sa.DateTime(), nullable=True)
    )

    # server_default pra nao quebrar fornecedores ja existentes em
    # producao (NOT NULL sem default falharia com linhas ja gravadas) --
    # nao removido depois de aplicar, mantido junto do model pra
    # combinar com o default declarado no Fornecedor.margem_padrao.
    op.add_column(
        'fornecedores',
        sa.Column(
            'margem_padrao',
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default='0',
        ),
    )

    # NAO mexe em refresh_tokens_token_key -- drift do autogenerate sem
    # relacao com esta mudanca (fora de escopo desta migration).


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_column('fornecedores', 'margem_padrao')
    op.drop_column('compras', 'cancelado_em')
