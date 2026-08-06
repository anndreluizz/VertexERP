from datetime import datetime

from pydantic import BaseModel


class MovimentoFiadoBase(BaseModel):
    cliente_id: int
    venda_id: int | None = None
    tipo: str
    valor: float
    descricao: str | None = None
    forma_pagamento: str | None = None
    data: datetime | None = None


class MovimentoFiadoCreate(MovimentoFiadoBase):
    pass


class MovimentoFiadoUpdate(BaseModel):
    # correcao de um lancamento errado -- so valor/descricao, o resto
    # (tipo, cliente, forma de pagamento) nao muda depois de criado.
    valor: float | None = None
    descricao: str | None = None


class MovimentoFiadoResponse(MovimentoFiadoBase):
    id: int
    usuario_id: int
    data: datetime

    class Config:
        orm_mode = True


class SaldoFiadoResponse(BaseModel):
    cliente_id: int
    saldo: float
