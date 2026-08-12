from datetime import datetime

from pydantic import BaseModel


class CaixaBase(BaseModel):
    saldo_inicial: float


class CaixaCreate(CaixaBase):
    pass


class CaixaResponse(BaseModel):
    id: int
    data_abertura: datetime
    data_fechamento: datetime | None = None
    saldo_inicial: float
    saldo_final: float
    status: str

    class Config:
        orm_mode = True