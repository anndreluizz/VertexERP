from datetime import datetime

from app.schemas.base import Schema


class LojaCreate(Schema):
    nome: str


class LojaUpdate(Schema):
    nome: str | None = None
    ativa: bool | None = None


class LojaResponse(Schema):
    id: int
    nome: str
    ativa: bool
    criado_em: datetime
