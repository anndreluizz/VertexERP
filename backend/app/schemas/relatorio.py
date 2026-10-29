from datetime import datetime
from decimal import Decimal

from app.schemas.base import Quantidade, Schema


class KpiValor(Schema):
    atual: Decimal
    anterior: Decimal
    variacao_pct: float | None = None
class VendaPorDia(Schema):
    data: str
    total: Decimal


class ProdutoMaisVendido(Schema):
    produto: str
    quantidade: Quantidade
    total: Decimal


class FormaPagamentoTotal(Schema):
    forma_pagamento: str
    quantidade: int
    total: Decimal


class VendaResumo(Schema):
    id: int
    data: datetime
    cliente: str | None = None
    valor_total: Decimal
    forma_pagamento: str
    status: str


class ComparativoLojaItem(Schema):
    loja_id: int
    loja_nome: str
    receita_total: Decimal
    lucro: Decimal
    quantidade_vendas: int
    ticket_medio: Decimal
    margem_lucro: Decimal
    custo_incompleto: bool = False


class FunilVendasResponse(Schema):
    suspensas_agora: int
    finalizadas: int
    canceladas: int
    taxa_cancelamento: Decimal


class MargemCategoriaItem(Schema):
    categoria: str
    receita: Decimal
    lucro: Decimal
    margem_pct: Decimal
    quantidade: Quantidade
    custo_incompleto: bool = False


class EstoqueCategoriaItem(Schema):
    categoria: str
    quantidade: Quantidade
    valor: Decimal


class VendaDiaSemanaItem(Schema):
    dia_semana: str
    quantidade: int
    total: Decimal


class VendaDiaSemanaHoraItem(Schema):
    dia_semana: str
    hora: int
    quantidade: int
    total: Decimal


class MesAMesItem(Schema):
    """Um mes do quadro "Mes a mes" (Relatorios)."""
    mes: int
    faturamento: Decimal
    quantidade_vendas: int
    ticket_medio: Decimal
    lucro: Decimal
    custo_incompleto: bool
    entrou: Decimal
    vendido_fiado: Decimal
    fiado_recebido: Decimal
    contas_pagas: Decimal
    sangrias: Decimal
    sobrou: Decimal


class GastoCompraMensalItem(Schema):
    mes: str
    total: Decimal


class RankingFornecedorItem(Schema):
    fornecedor_id: int
    nome: str
    quantidade_compras: int
    total: Decimal


class PrazoFornecedorItem(Schema):
    fornecedor_id: int
    nome: str
    prazo_medio_dias: float
    quantidade_parcelas: int


class CategoriaSemVendaItem(Schema):
    categoria: str
    ultima_venda: datetime | None = None
    dias_sem_venda: int | None = None
class CurvaAbcItem(Schema):
    produto_id: int
    produto: str
    quantidade: Quantidade
    total: Decimal
    percentual: float
    percentual_acumulado: float
    classe: str


class ComparativoEstoqueLojaItem(Schema):
    loja_id: int
    loja_nome: str
    quantidade_total: Quantidade
    valor_em_estoque: Decimal
    produtos_abaixo_minimo: int


class SugestaoReposicaoItem(Schema):
    produto_id: int
    produto: str
    quantidade_atual: Quantidade
    estoque_minimo: Quantidade
    quantidade_sugerida: Quantidade


class RelatorioVendasResponse(Schema):
    receita_total: KpiValor
    lucro: KpiValor
    quantidade_vendas: KpiValor
    ticket_medio: KpiValor
    clientes_atendidos: KpiValor
    produtos_vendidos: KpiValor
    margem_lucro: KpiValor
    custo_incompleto: bool = False
    vendas_por_dia: list[VendaPorDia]
    top_produtos: list[ProdutoMaisVendido]
    formas_pagamento: list[FormaPagamentoTotal]
    vendas_total: int
    vendas: list[VendaResumo]
