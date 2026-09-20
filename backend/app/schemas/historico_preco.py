from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class HistoricoPrecoResponse(BaseModel):
    id: int
    usuario_id: int
    usuario_nome: str | None = None
    preco_custo_anterior: Decimal
    preco_custo_novo: Decimal
    preco_venda_anterior: Decimal
    preco_venda_novo: Decimal
    data: datetime

    class Config:
        orm_mode = True
