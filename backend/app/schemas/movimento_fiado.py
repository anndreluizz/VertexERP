from datetime import datetime

from pydantic import BaseModel


class MovimentoFiadoBase(BaseModel):
    cliente_id: int
    venda_id: int | None = None
    tipo: str
    valor: float
    descricao: str | None = None
    forma_pagamento: str | None = None


class MovimentoFiadoCreate(MovimentoFiadoBase):
    pass


class MovimentoFiadoResponse(MovimentoFiadoBase):
    id: int
    usuario_id: int
    data: datetime

    class Config:
        orm_mode = True


class SaldoFiadoResponse(BaseModel):
    cliente_id: int
    saldo: float
