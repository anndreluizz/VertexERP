from datetime import datetime

from app.schemas.base import Schema


class CategoriaDespesaCreate(Schema):
    nome: str


class CategoriaDespesaUpdate(Schema):
    nome: str


class CategoriaDespesaResponse(Schema):
    id: int
    nome: str
    criado_em: datetime
