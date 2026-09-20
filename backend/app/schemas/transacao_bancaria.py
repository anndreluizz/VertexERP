from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class OfxImportarRequest(BaseModel):
    ofx_conteudo: str


class TransacaoPreview(BaseModel):
    fitid: str
    data: date
    descricao: str
    valor: Decimal
    tipo: str
    ja_importada: bool


class OfxPreviewResponse(BaseModel):
    banco: str | None = None
    conta: str | None = None
    transacoes: list[TransacaoPreview]
    total_novas: int
    total_ja_importadas: int


class OfxImportarResultado(BaseModel):
    total_importadas: int


class TransacaoBancariaResponse(BaseModel):
    id: int
    loja_id: int | None = None
    fitid: str
    data: date
    descricao: str | None = None
    valor: Decimal
    tipo: str
    status: str
    conta_pagar_id: int | None = None
    conta_pagar_descricao: str | None = None
    conta_receber_id: int | None = None
    conta_receber_descricao: str | None = None
    conciliado_em: datetime | None = None
    conciliado_por_nome: str | None = None

    class Config:
        orm_mode = True


class ConciliarRequest(BaseModel):
    conta_pagar_id: int | None = None
    conta_receber_id: int | None = None


class CandidatoConciliacao(BaseModel):
    tipo: str  # PAGAR ou RECEBER
    id: int
    descricao: str
    valor: Decimal
    data: datetime
