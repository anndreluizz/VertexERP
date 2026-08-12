from pydantic import BaseModel


class SerieMensalItem(BaseModel):

    mes: str

    valor: float


class DashboardResponse(BaseModel):

    vendas_hoje: float

    vendas_hoje_qtd: int

    vendas_mes: float

    compras_hoje: float

    saldo_caixa: float

    contas_receber: float

    contas_pagar: float

    total_fiado_devedor: float

    clientes: int

    fornecedores: int

    produtos: int

    estoque_baixo: int

    contas_vencidas_qtd: int

    contas_vencidas_valor: float

    contas_vencendo_hoje_qtd: int

    contas_vencendo_hoje_valor: float

    contas_pagas_hoje_qtd: int

    contas_pagas_hoje_valor: float

    fiado_recebido_hoje: float

    contas_mes_pago: float

    contas_mes_pendente: float

    serie_recebimentos_mensal: list[SerieMensalItem]

    serie_pagamentos_mensal: list[SerieMensalItem]
