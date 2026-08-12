"""adiciona numero_boleto em contas_pagar

Revision ID: e154ba616fe0
Revises: 64539f99fb98
Create Date: 2026-07-16 14:43:43.780706

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e154ba616fe0'
down_revision: Union[str, Sequence[str], None] = '64539f99fb98'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nota: o autogenerate original também detectou a tabela `mesas` e
    # colunas órfãs em `vendas`/`itens_venda` (restos do Mesa/Comanda,
    # removido do código-fonte) como "removidos". Isso foi deixado de
    # fora de propósito — são DROPs destrutivos que não fazem parte
    # desta mudança e precisam de confirmação antes de rodar.
    op.add_column('contas_pagar', sa.Column('numero_boleto', sa.String(length=60), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('contas_pagar', 'numero_boleto')
