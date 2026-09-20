from datetime import datetime

from pydantic import BaseModel


class CentroCustoCreate(BaseModel):
    nome: str


class CentroCustoUpdate(BaseModel):
    nome: str


class CentroCustoResponse(BaseModel):
    id: int
    nome: str
    criado_em: datetime

    class Config:
        orm_mode = True
