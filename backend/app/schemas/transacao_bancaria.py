from datetime import date, datetime
from decimal import Decimal

from app.schemas.base import Schema


class OfxImportarRequest(Schema):
    ofx_conteudo: str


class TransacaoPreview(Schema):
    fitid: str
    data: date
    descricao: str
    valor: Decimal
    tipo: str
    ja_importada: bool


class OfxPreviewResponse(Schema):
    banco: str | None = None
    conta: str | None = None
    transacoes: list[TransacaoPreview]
    total_novas: int
    total_ja_importadas: int


class OfxImportarResultado(Schema):
    total_importadas: int


class TransacaoBancariaResponse(Schema):
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
    conciliado_em: datetime | None = None
    conciliado_por_nome: str | None = None


class ConciliarRequest(Schema):
    conta_pagar_id: int | None = None


class CandidatoConciliacao(Schema):
    tipo: str  # PAGAR
    id: int
    descricao: str
    valor: Decimal
    data: datetime
