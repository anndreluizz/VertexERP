from datetime import datetime

from pydantic import BaseModel


class CategoriaDespesaCreate(BaseModel):
    nome: str


class CategoriaDespesaUpdate(BaseModel):
    nome: str


class CategoriaDespesaResponse(BaseModel):
    id: int
    nome: str
    criado_em: datetime

    class Config:
        orm_mode = True
