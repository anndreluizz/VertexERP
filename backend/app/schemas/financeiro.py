from datetime import datetime
from decimal import Decimal

from app.schemas.base import Schema


class ItemFluxoCaixa(Schema):
    tipo: str  # "A_RECEBER" ou "A_PAGAR"
    data_vencimento: datetime
    descricao: str | None = None
    valor: Decimal


class FluxoCaixaResponse(Schema):
    saldo_atual: Decimal
    total_a_receber: Decimal
    total_a_pagar: Decimal
    saldo_projetado: Decimal
    itens: list[ItemFluxoCaixa]
