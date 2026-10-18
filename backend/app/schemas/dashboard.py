from decimal import Decimal

from app.schemas.base import Schema


class SerieMensalItem(Schema):

    mes: str

    valor: Decimal


class VendaDiariaItem(Schema):

    data: str

    total: Decimal


class DashboardResponse(Schema):

    vendas_hoje: Decimal

    vendas_hoje_qtd: int

    vendas_ontem: Decimal

    vendas_ultimos_7_dias: list[VendaDiariaItem]

    vendas_mes: Decimal

    compras_hoje: Decimal

    saldo_caixa: Decimal

    contas_receber: Decimal

    total_fiado_devedor: Decimal

    contas_pagar: Decimal

    clientes: int

    fornecedores: int

    produtos: int

    estoque_baixo: int

    contas_vencidas_qtd: int

    contas_vencidas_valor: Decimal

    contas_vencendo_hoje_qtd: int

    contas_vencendo_hoje_valor: Decimal

    contas_pagas_hoje_qtd: int

    contas_pagas_hoje_valor: Decimal

    fiado_recebido_hoje: Decimal

    contas_mes_pago: Decimal

    contas_mes_pendente: Decimal

    serie_recebimentos_mensal: list[SerieMensalItem]

    serie_pagamentos_mensal: list[SerieMensalItem]
