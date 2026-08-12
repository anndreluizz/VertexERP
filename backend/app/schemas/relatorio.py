from datetime import datetime

from pydantic import BaseModel


class KpiValor(BaseModel):
    atual: float
    anterior: float
    variacao_pct: float | None


class VendaPorDia(BaseModel):
    data: str
    total: float


class ProdutoMaisVendido(BaseModel):
    produto: str
    quantidade: int
    total: float


class FormaPagamentoTotal(BaseModel):
    forma_pagamento: str
    quantidade: int
    total: float


class VendaResumo(BaseModel):
    id: int
    data: datetime
    cliente: str | None
    valor_total: float
    forma_pagamento: str
    status: str


class RelatorioVendasResponse(BaseModel):
    receita_total: KpiValor
    lucro: KpiValor
    quantidade_vendas: KpiValor
    ticket_medio: KpiValor
    clientes_atendidos: KpiValor
    produtos_vendidos: KpiValor
    margem_lucro: KpiValor
    vendas_por_dia: list[VendaPorDia]
    top_produtos: list[ProdutoMaisVendido]
    formas_pagamento: list[FormaPagamentoTotal]
    vendas_total: int
    vendas: list[VendaResumo]
