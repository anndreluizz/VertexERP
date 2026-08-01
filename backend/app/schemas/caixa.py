from datetime import datetime

from pydantic import BaseModel


class CaixaBase(BaseModel):
    saldo_inicial: float


class CaixaCreate(CaixaBase):
    pass


class FecharCaixaRequest(BaseModel):
    valor_contado: float | None = None
    observacoes: str | None = None


class CaixaResponse(BaseModel):
    id: int
    data_abertura: datetime
    data_fechamento: datetime | None = None
    saldo_inicial: float
    saldo_final: float
    status: str
    valor_contado: float | None = None
    observacoes: str | None = None
    usuario_id: int | None = None

    class Config:
        orm_mode = True


class ResumoCaixaResponse(BaseModel):
    saldo_inicial: float
    vendas_dinheiro: float
    vendas_pix: float
    vendas_cartao: float
    vendas_prazo: float
    suprimentos: float
    sangrias: float
    recebimentos_fiado: float
    total_previsto: float
    total_geral: float
