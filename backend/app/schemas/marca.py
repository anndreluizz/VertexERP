from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MarcaCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None


class MarcaUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    ativo: Optional[bool] = None


class MarcaResponse(BaseModel):
    id: int
    nome: str
    descricao: Optional[str]
    ativo: bool
    criado_em: datetime

    class Config:
        orm_mode = True
