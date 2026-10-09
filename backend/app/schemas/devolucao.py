from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, conint, constr

from app.enums.forma_pagamento import FormaPagamento


class ItemDevolucaoCreate(BaseModel):
    item_venda_id: int
    quantidade: conint(gt=0)


class DevolucaoCreate(BaseModel):
    itens: list[ItemDevolucaoCreate]
    # BOLETO não faz sentido pra devolver dinheiro; PRAZO = abater do fiado
    forma_reembolso: FormaPagamento = FormaPagamento.DINHEIRO
    motivo: constr(max_length=255) | None = None


class ItemDevolucaoResponse(BaseModel):
    item_venda_id: int
    produto_id: int
    produto_nome: str | None = None
    quantidade: int
    valor: Decimal

    class Config:
        orm_mode = True


class DevolucaoResponse(BaseModel):
    id: int
    venda_id: int
    usuario_id: int | None = None
    usuario_nome: str | None = None
    data: datetime
    valor_total: Decimal
    forma_reembolso: str
    motivo: str | None = None
    itens: list[ItemDevolucaoResponse]

    class Config:
        orm_mode = True
