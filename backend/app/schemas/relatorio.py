from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class KpiValor(BaseModel):
    atual: Decimal
    anterior: Decimal
    variacao_pct: float | None


class VendaPorDia(BaseModel):
    data: str
    total: Decimal


class ProdutoMaisVendido(BaseModel):
    produto: str
    quantidade: int
    total: Decimal


class FormaPagamentoTotal(BaseModel):
    forma_pagamento: str
    quantidade: int
    total: Decimal


class VendaResumo(BaseModel):
    id: int
    data: datetime
    cliente: str | None
    valor_total: Decimal
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
