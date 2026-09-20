from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.enums.forma_pagamento import FormaPagamento


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

    forma_pagamento: FormaPagamento

    data_vencimento: datetime | None = None

    numero_parcelas: int = 1

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

    cancelado_em: datetime | None

    itens: list[ItemCompraResponse]

    class Config:
        orm_mode = True
