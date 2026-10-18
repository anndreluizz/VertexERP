from datetime import datetime
from decimal import Decimal

from app.schemas.base import Schema


class HistoricoPrecoResponse(Schema):
    id: int
    usuario_id: int
    usuario_nome: str | None = None
    preco_custo_anterior: Decimal
    preco_custo_novo: Decimal
    preco_venda_anterior: Decimal
    preco_venda_novo: Decimal
    data: datetime
