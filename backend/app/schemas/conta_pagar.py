from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ContaPagarBase(BaseModel):
    fornecedor_id: int | None = None
    compra_id: int | None = None
    data_vencimento: datetime
    valor: Decimal
    observacao: str | None = None


class ContaPagarCreate(ContaPagarBase):
    pass


class ContaPagarUpdate(BaseModel):
    data_vencimento: datetime | None = None
    valor: Decimal | None = None
    observacao: str | None = None
    status: str | None = None


class ContaPagarResponse(BaseModel):
    id: int

    fornecedor_id: int | None

    compra_id: int | None

    data_emissao: datetime

    data_vencimento: datetime

    data_pagamento: datetime | None

    valor: Decimal

    observacao: str | None

    status: str

    class Config:
        orm_mode = True