from datetime import datetime
from decimal import Decimal

from pydantic import constr

from app.schemas.base import Quantidade, QuantidadePositiva, Schema
from app.enums.forma_pagamento import FormaPagamento


class ItemDevolucaoCreate(Schema):
    item_venda_id: int
    quantidade: QuantidadePositiva


class DevolucaoCreate(Schema):
    itens: list[ItemDevolucaoCreate]
    # BOLETO não faz sentido pra devolver dinheiro; PRAZO = abater do fiado
    forma_reembolso: FormaPagamento = FormaPagamento.DINHEIRO
    motivo: constr(max_length=255) | None = None


class ItemDevolucaoResponse(Schema):
    item_venda_id: int
    produto_id: int
    produto_nome: str | None = None
    quantidade: Quantidade
    valor: Decimal


class DevolucaoResponse(Schema):
    id: int
    venda_id: int
    usuario_id: int | None = None
    usuario_nome: str | None = None
    data: datetime
    valor_total: Decimal
    forma_reembolso: str
    motivo: str | None = None
    itens: list[ItemDevolucaoResponse]
