"""seed estoque_loja da matriz a partir de produto.estoque

Revision ID: f791564ca95a
Revises: 7596e4010a1f
Create Date: 2026-09-14 20:22:59.960865

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f791564ca95a'
down_revision: Union[str, Sequence[str], None] = '7596e4010a1f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # todo estoque que existe hoje esta fisicamente na Matriz -- uma
    # loja nova (Filial) comeca em 0 pra cada produto ate ser
    # abastecida de verdade, nunca herda essa quantidade (ver
    # EstoqueLojaRepository.obter_ou_criar)
    op.execute(
        "INSERT INTO estoque_lojas (produto_id, loja_id, quantidade, estoque_minimo) "
        "SELECT p.id, l.id, p.estoque, p.estoque_minimo "
        "FROM produtos p, lojas l "
        "WHERE l.nome = 'Matriz'"
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.execute(
        "DELETE FROM estoque_lojas WHERE loja_id = "
        "(SELECT id FROM lojas WHERE nome = 'Matriz')"
    )
