"""horarios gerados pelo servidor: UTC -> hora local

Ate aqui o backend gravava os horarios que ele mesmo gera (hora da
venda, do fiado, do caixa, das contas, notificacoes...) com
datetime.utcnow(), mas as telas mostram sem converter -- tudo aparecia
4h adiantado (UTC-4) e o "vendas de hoje" virava o dia as 20h. A partir
desta versao o backend grava datetime.now(); esta migracao traz o
historico pro mesmo fuso.

So mexe nas colunas geradas pelo servidor. Datas digitadas pelo usuario
(vencimento etc.) ja eram hora local e ficam de fora. Em
movimentos_fiado.data o Desktop tambem manda data escolhida a mao, sempre
a meia-noite em ponto -- por isso nenhuma coluna mexe em valores com
hora exatamente 00:00:00 (os do servidor sempre tem segundos/micro).

Expiracao de sessao/token continua em UTC (so comparada com utcnow no
proprio backend).

Revision ID: d4e7a1c9b2f0
Revises: 56a4bd6fe829
Create Date: 2026-09-24
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op


revision: str = "d4e7a1c9b2f0"
down_revision: Union[str, Sequence[str], None] = "56a4bd6fe829"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUNAS = [
    ("caixa", "data_abertura"),
    ("caixa", "data_fechamento"),
    ("categorias", "criado_em"),
    ("categorias_despesa", "criado_em"),
    ("centros_custo", "criado_em"),
    ("cliente_observacoes", "criado_em"),
    ("clientes", "criado_em"),
    ("compras", "data"),
    ("compras", "cancelado_em"),
    ("comprovante_envios", "data"),
    ("contagens_estoque", "criado_em"),
    ("contagens_estoque", "finalizado_em"),
    ("contas_pagar", "data_emissao"),
    ("contas_pagar", "data_pagamento"),
    ("contas_pagar_eventos", "data"),
    ("contas_receber", "data_emissao"),
    ("contas_receber", "data_recebimento"),
    ("device_tokens", "criado_em"),
    ("device_tokens", "atualizado_em"),
    ("fornecedores", "criado_em"),
    ("historico_precos", "data"),
    ("logs_auditoria", "data"),
    ("lojas", "criado_em"),
    ("marcas", "criado_em"),
    ("movimentos_caixa", "data"),
    ("movimentos_estoque", "data"),
    ("movimentos_fiado", "data"),
    ("notificacoes", "criado_em"),
    ("produtos", "criado_em"),
    ("refresh_tokens", "criado_em"),
    ("refresh_tokens", "ultimo_uso_em"),
    ("solicitacoes_aprovacao", "criado_em"),
    ("solicitacoes_aprovacao", "resolvido_em"),
    ("transacoes_bancarias", "criado_em"),
    ("transacoes_bancarias", "conciliado_em"),
    ("transferencias_estoque", "data"),
    ("vendas", "data"),
    ("vendas", "cancelado_em"),
]


def _deslocamento_minutos() -> int:
    """Fuso do computador do servidor agora (ex.: -240 em UTC-4)."""
    return round(
        datetime.now(timezone.utc).astimezone().utcoffset().total_seconds()
        / 60
    )


def _aplicar(sinal: int) -> None:
    minutos = sinal * _deslocamento_minutos()
    if minutos == 0:
        return

    for tabela, coluna in COLUNAS:
        op.execute(
            f"UPDATE {tabela} "
            f"SET {coluna} = {coluna} + INTERVAL '{minutos} minutes' "
            f"WHERE {coluna} IS NOT NULL "
            f"AND {coluna}::time <> TIME '00:00:00'"
        )


def upgrade() -> None:
    _aplicar(+1)


def downgrade() -> None:
    _aplicar(-1)
