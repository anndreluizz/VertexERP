from datetime import datetime

from pydantic import BaseModel


class LojaCreate(BaseModel):
    nome: str


class LojaUpdate(BaseModel):
    nome: str | None = None
    ativa: bool | None = None


class LojaResponse(BaseModel):
    id: int
    nome: str
    ativa: bool
    criado_em: datetime

    class Config:
        orm_mode = True
