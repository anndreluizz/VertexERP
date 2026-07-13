from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ItemCompraCreate(BaseModel):
    produto_id: int
    quantidade: int
    valor_unitario: Decimal


class ItemCompraResponse(BaseModel):
    id: int
    produto_id: int
    quantidade: int
    valor_unitario: Decimal
    subtotal: Decimal

    class Config:
        orm_mode = True


class CompraCreate(BaseModel):

    fornecedor_id: int

    observacao: str | None = None

    forma_pagamento: str

    data_vencimento: datetime | None = None

    itens: list[ItemCompraCreate]


class CompraResponse(BaseModel):

    id: int

    fornecedor_id: int

    data: datetime

    valor_total: Decimal

    observacao: str | None

    status: str

    forma_pagamento: str

    data_vencimento: datetime | None

    itens: list[ItemCompraResponse]

    class Config:
        orm_mode = True