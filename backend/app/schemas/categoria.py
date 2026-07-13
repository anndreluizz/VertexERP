from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CategoriaCreate(BaseModel):
    nome: str
    descricao: Optional[str] = None


class CategoriaUpdate(BaseModel):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    ativo: Optional[bool] = None


class CategoriaResponse(BaseModel):
    id: int
    nome: str
    descricao: Optional[str]
    ativo: bool
    criado_em: datetime

    class Config:
        orm_mode = True