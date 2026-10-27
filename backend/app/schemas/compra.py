from datetime import datetime
from decimal import Decimal

from app.schemas.base import Quantidade, Schema
from app.enums.forma_pagamento import FormaPagamento


class ItemCompraCreate(Schema):
    produto_id: int
    quantidade: Quantidade
    valor_unitario: Decimal


class ItemCompraResponse(Schema):
    id: int
    produto_id: int
    quantidade: Quantidade
    valor_unitario: Decimal
    subtotal: Decimal


class CompraCreate(Schema):

    fornecedor_id: int

    observacao: str | None = None

    forma_pagamento: FormaPagamento

    data_vencimento: datetime | None = None

    numero_parcelas: int = 1

    itens: list[ItemCompraCreate]


class CompraResponse(Schema):

    id: int

    fornecedor_id: int

    data: datetime

    valor_total: Decimal

    observacao: str | None = None
    status: str

    forma_pagamento: str

    data_vencimento: datetime | None = None
    cancelado_em: datetime | None = None
    itens: list[ItemCompraResponse]
