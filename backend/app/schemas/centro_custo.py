from datetime import datetime

from app.schemas.base import Schema


class CentroCustoCreate(Schema):
    nome: str


class CentroCustoUpdate(Schema):
    nome: str


class CentroCustoResponse(Schema):
    id: int
    nome: str
    criado_em: datetime
