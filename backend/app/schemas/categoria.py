from datetime import datetime
from typing import Optional

from app.schemas.base import Schema


class CategoriaCreate(Schema):
    nome: str
    descricao: Optional[str] = None


class CategoriaUpdate(Schema):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    ativo: Optional[bool] = None


class CategoriaResponse(Schema):
    id: int
    nome: str
    descricao: Optional[str] = None
    ativo: bool
    criado_em: datetime
