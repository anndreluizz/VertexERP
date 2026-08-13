from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ItemFluxoCaixa(BaseModel):
    tipo: str  # "A_RECEBER" ou "A_PAGAR"
    data_vencimento: datetime
    descricao: str | None
    valor: Decimal


class FluxoCaixaResponse(BaseModel):
    saldo_atual: Decimal
    total_a_receber: Decimal
    total_a_pagar: Decimal
    saldo_projetado: Decimal
    itens: list[ItemFluxoCaixa]
