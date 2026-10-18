from datetime import datetime
from typing import Optional

from app.schemas.base import Schema


class MarcaCreate(Schema):
    nome: str
    descricao: Optional[str] = None


class MarcaUpdate(Schema):
    nome: Optional[str] = None
    descricao: Optional[str] = None
    ativo: Optional[bool] = None


class MarcaResponse(Schema):
    id: int
    nome: str
    descricao: Optional[str] = None
    ativo: bool
    criado_em: datetime
