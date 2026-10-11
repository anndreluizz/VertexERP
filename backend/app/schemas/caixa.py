from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CaixaBase(BaseModel):
    saldo_inicial: Decimal


class CaixaCreate(CaixaBase):
    pass


class FecharCaixaRequest(BaseModel):
    valor_contado: Decimal | None = None
    observacoes: str | None = None


class CaixaResponse(BaseModel):
    id: int
    data_abertura: datetime
    data_fechamento: datetime | None = None
    saldo_inicial: Decimal
    saldo_final: Decimal
    status: str
    valor_contado: Decimal | None = None
    observacoes: str | None = None
    usuario_id: int | None = None
    usuario_nome: str | None = None  # so' no /historico

    class Config:
        orm_mode = True


class ResumoCaixaResponse(BaseModel):
    saldo_inicial: Decimal
    vendas_dinheiro: Decimal
    vendas_pix: Decimal
    vendas_cartao: Decimal
    vendas_prazo: Decimal
    suprimentos: Decimal
    sangrias: Decimal
    recebimentos_fiado: Decimal
    total_previsto: Decimal
    total_geral: Decimal


class EntradasCaixaResponse(BaseModel):
    """Dinheiro que entrou no periodo (ver CaixaService.entradas)."""
    dinheiro: Decimal
    pix: Decimal
    cartao: Decimal
    outros: Decimal
    fiado_recebido: Decimal  # ja incluido nas formas acima
    total: Decimal
    sangrias: Decimal
    vendas_prazo: Decimal
    contas_pagas: Decimal
    sobrou: Decimal  # total - contas_pagas - sangrias
