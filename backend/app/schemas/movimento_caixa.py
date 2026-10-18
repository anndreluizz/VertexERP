from datetime import datetime
from decimal import Decimal

from app.schemas.base import Schema


class MovimentoCaixaBase(Schema):
    tipo: str
    descricao: str | None = None
    valor: Decimal


class MovimentoCaixaCreate(MovimentoCaixaBase):
    pass


class MovimentoCaixaResponse(MovimentoCaixaBase):
    id: int
    caixa_id: int
    usuario_id: int
    venda_id: int | None = None
    data: datetime
