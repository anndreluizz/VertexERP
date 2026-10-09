from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class MovimentoFiadoBase(BaseModel):
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


class MovimentoFiadoUpdate(BaseModel):
    # correcao de um lancamento errado -- so valor/descricao, o resto
    # (tipo, cliente, forma de pagamento) nao muda depois de criado.
    valor: Decimal | None = None
    descricao: str | None = None


class MovimentoFiadoResponse(MovimentoFiadoBase):
    id: int
    usuario_id: int
    data: datetime

    class Config:
        orm_mode = True


class SaldoFiadoResponse(BaseModel):
    cliente_id: int
    saldo: Decimal


class FichaFiadoResponse(BaseModel):
    """Visão completa do fiado de um cliente -- saldo já calculado +
    histórico de movimentos, tudo numa chamada só (evita a tela de
    ficha do cliente ter que buscar saldo e movimentos separado)."""

    cliente_id: int
    nome: str
    saldo_devedor: Decimal
    movimentos: list[MovimentoFiadoResponse]

    class Config:
        orm_mode = True


class RegistrarPagamentoFiadoRequest(BaseModel):
    cliente_id: int
    valor: Decimal
    descricao: str | None = None
    data: datetime | None = None


class RegistrarCompraFiadoRequest(BaseModel):
    cliente_id: int
    valor: Decimal
    descricao: str | None = None
    data: datetime | None = None
