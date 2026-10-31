from datetime import datetime
from decimal import Decimal

from app.schemas.base import Schema


class MovimentoFiadoBase(Schema):
    cliente_id: int
    venda_id: int | None = None
    tipo: str
    valor: Decimal
    descricao: str | None = None
    forma_pagamento: str | None = None
    data: datetime | None = None


class MovimentoFiadoCreate(MovimentoFiadoBase):
    # "Compra fiada" lancada pela ficha do cliente: alem do fiado, vira
    # uma venda a prazo (sem itens de produto) pra contar na tela de
    # Vendas, no total da vendedora e no faturamento. "Divida anterior"
    # manda False -- e debito antigo do caderno, nao venda de hoje.
    registrar_venda: bool = False


class MovimentoFiadoUpdate(Schema):
    # correcao de um lancamento errado -- valor/descricao e, num
    # PAGAMENTO que entrou no caixa, a forma (pagou no PIX, marcaram
    # Dinheiro). Tipo e cliente nao mudam depois de criado.
    valor: Decimal | None = None
    descricao: str | None = None
    forma_pagamento: str | None = None


class MovimentoFiadoResponse(MovimentoFiadoBase):
    id: int
    usuario_id: int
    data: datetime


class SaldoFiadoResponse(Schema):
    cliente_id: int
    saldo: Decimal


class FichaFiadoResponse(Schema):
    """Visão completa do fiado de um cliente -- saldo já calculado +
    histórico de movimentos, tudo numa chamada só (evita a tela de
    ficha do cliente ter que buscar saldo e movimentos separado)."""

    cliente_id: int
    nome: str
    saldo_devedor: Decimal
    movimentos: list[MovimentoFiadoResponse]


class RegistrarPagamentoFiadoRequest(Schema):
    cliente_id: int
    valor: Decimal
    descricao: str | None = None
    data: datetime | None = None


class RegistrarCompraFiadoRequest(Schema):
    cliente_id: int
    valor: Decimal
    descricao: str | None = None
    data: datetime | None = None
