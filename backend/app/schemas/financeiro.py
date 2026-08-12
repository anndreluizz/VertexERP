from datetime import datetime

from pydantic import BaseModel


class ItemFluxoCaixa(BaseModel):
    tipo: str  # "A_RECEBER" ou "A_PAGAR"
    data_vencimento: datetime
    descricao: str | None
    valor: float


class FluxoCaixaResponse(BaseModel):
    saldo_atual: float
    total_a_receber: float
    total_a_pagar: float
    saldo_projetado: float
    itens: list[ItemFluxoCaixa]
