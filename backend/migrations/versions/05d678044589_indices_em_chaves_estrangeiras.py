"""indices em chaves estrangeiras

Nenhuma coluna de chave estrangeira do sistema tinha indice ate agora
-- FK cria uma restricao de integridade, mas NAO cria indice sozinha
(diferenca comum de confundir). Na pratica, toda consulta que filtra
por essas colunas (ficha do cliente, itens de uma venda, historico de
estoque de um produto, caixa aberto, etc. -- basicamente a maioria das
telas do sistema) faz uma varredura sequencial da tabela inteira, toda
vez. Com poucas linhas isso passa despercebido, mas fica cada vez mais
lento a medida que o volume de vendas/movimentos cresce -- causa
provavel de lentidao reportada durante o uso normal.

Revision ID: 05d678044589
Revises: 94aa5becbd7a
Create Date: 2026-09-10 13:22:28.038645

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05d678044589'
down_revision: Union[str, Sequence[str], None] = '94aa5becbd7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tabela, coluna) -- toda coluna de chave estrangeira do sistema que
# ainda nao tinha indice, mais o status de solicitacoes_aprovacao
# (filtrado o tempo todo pelo polling de solicitacoes pendentes).
_INDICES = [
    ("vendas", "cliente_id"),
    ("vendas", "usuario_id"),
    ("vendas", "cancelado_por_id"),
    ("itens_venda", "venda_id"),
    ("itens_venda", "produto_id"),
    ("movimentos_fiado", "cliente_id"),
    ("movimentos_fiado", "venda_id"),
    ("movimentos_fiado", "usuario_id"),
    ("movimentos_caixa", "caixa_id"),
    ("movimentos_caixa", "usuario_id"),
    ("movimentos_estoque", "produto_id"),
    ("movimentos_estoque", "usuario_id"),
    ("cliente_observacoes", "cliente_id"),
    ("cliente_observacoes", "usuario_id"),
    ("caixa", "usuario_id"),
    ("compras", "fornecedor_id"),
    ("itens_compra", "compra_id"),
    ("itens_compra", "produto_id"),
    ("contas_pagar", "fornecedor_id"),
    ("contas_pagar", "compra_id"),
    ("contas_pagar_eventos", "usuario_id"),
    ("contas_receber", "cliente_id"),
    ("contas_receber", "venda_id"),
    ("comprovante_envios", "usuario_id"),
    ("device_tokens", "usuario_id"),
    ("refresh_tokens", "usuario_id"),
    ("solicitacoes_aprovacao", "solicitante_id"),
    ("solicitacoes_aprovacao", "aprovador_id"),
    ("solicitacoes_aprovacao", "status"),
]


def upgrade() -> None:
    """Upgrade schema."""
    for tabela, coluna in _INDICES:
        op.create_index(
            f"ix_{tabela}_{coluna}", tabela, [coluna], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    for tabela, coluna in reversed(_INDICES):
        op.drop_index(f"ix_{tabela}_{coluna}", table_name=tabela)
