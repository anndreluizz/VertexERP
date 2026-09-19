"""seed estoque_minimo por loja a partir de produto

Revision ID: c3d7714b9466
Revises: 5ad2aca6aae1
Create Date: 2026-09-19 11:30:30.294735

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d7714b9466'
down_revision: Union[str, Sequence[str], None] = '5ad2aca6aae1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # EstoqueLoja.estoque_minimo nunca foi lido por nenhum codigo ate
    # agora -- todo valor que existe hoje ali e' artefato (0 do default
    # antigo de EstoqueLojaRepository.obter_ou_criar, ou a copia unica
    # feita so' pra Matriz em f791564ca95a), nunca uma configuracao
    # deliberada de alguem. Seguro sobrescrever tudo com o minimo
    # GLOBAL do produto (Produto.estoque_minimo), pra nenhuma loja
    # "perder" o alerta que ja estava configurado la no dia em que o
    # codigo passa a ler esse campo por loja de verdade.
    op.execute(
        "UPDATE estoque_lojas "
        "SET estoque_minimo = produtos.estoque_minimo "
        "FROM produtos "
        "WHERE estoque_lojas.produto_id = produtos.id"
    )


def downgrade() -> None:
    """Downgrade schema."""

    # reverte pro default antigo (0) -- nao ha como recuperar os
    # valores anteriores ao upgrade, mas eles nunca foram usados por
    # nenhum codigo, entao nao ha estado "de verdade" a perder.
    op.execute("UPDATE estoque_lojas SET estoque_minimo = 0")
