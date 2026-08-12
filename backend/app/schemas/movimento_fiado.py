from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.enums.tipo_movimento_fiado import TipoMovimentoFiado


class PagamentoFiadoCreate(BaseModel):
    cliente_id: int
    valor: Decimal
    descricao: str | None = None
    data: datetime | None = None


class CompraFiadoCreate(BaseModel):
    cliente_id: int
    valor: Decimal
    descricao: str | None = None
    data: datetime | None = None


class MovimentoFiadoResponse(BaseModel):
    id: int
    cliente_id: int
    venda_id: int | None
    tipo: TipoMovimentoFiado
    valor: Decimal
    descricao: str | None
    data: datetime

    class Config:
        orm_mode = True


class FichaClienteResponse(BaseModel):
    cliente_id: int
    nome: str
    saldo_devedor: Decimal
    movimentos: list[MovimentoFiadoResponse]
