from datetime import datetime
from decimal import Decimal
from app.enums.forma_pagamento import FormaPagamento
from pydantic import BaseModel


class ItemVendaCreate(BaseModel):
    produto_id: int
    quantidade: int
    valor_unitario: Decimal


class ItemVendaResponse(BaseModel):
    id: int
    produto_id: int
    quantidade: int
    valor_unitario: Decimal
    subtotal: Decimal

    class Config:
        orm_mode = True


class VendaCreate(BaseModel):
    cliente_id: int | None = None

    observacao: str | None = None

    desconto: Decimal = Decimal("0.00")

    # AVISTA, PIX, DEBITO, CREDITO, BOLETO, PRAZO
    forma_pagamento: FormaPagamento = FormaPagamento.DINHEIRO

    # pagamento dividido (opcional, no maximo 2 formas): valor_forma_2
    # cobre parte do total nessa segunda forma, o restante fica na
    # forma_pagamento principal
    forma_pagamento_2: FormaPagamento | None = None
    valor_forma_2: Decimal | None = None

    data_vencimento: datetime | None = None

    itens: list[ItemVendaCreate]


class VendaResponse(BaseModel):
    id: int

    cliente_id: int | None

    data: datetime

    valor_total: Decimal

    desconto: Decimal

    observacao: str | None

    status: str

    forma_pagamento: FormaPagamento

    forma_pagamento_2: FormaPagamento | None = None
    valor_forma_2: Decimal | None = None

    data_vencimento: datetime | None = None

    itens: list[ItemVendaResponse]

    class Config:
        orm_mode = True