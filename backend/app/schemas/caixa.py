from datetime import datetime

from pydantic import BaseModel, ConfigDict


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

    model_config = ConfigDict(from_attributes=True)