from datetime import datetime
from decimal import Decimal

from pydantic import Field

from app.schemas.base import Schema


class CaixaBase(Schema):
    saldo_inicial: Decimal


class CaixaCreate(CaixaBase):
    pass


class FecharCaixaRequest(Schema):
    valor_contado: Decimal | None = None
    observacoes: str | None = None
    # pra onde vai o dinheiro da gaveta (o resto fica de troco)
    valor_guardado: Decimal | None = Field(None, ge=0)
    valor_retirado: Decimal | None = Field(None, ge=0)


class CaixaResponse(Schema):
    id: int
    data_abertura: datetime
    data_fechamento: datetime | None = None
    saldo_inicial: Decimal
    saldo_final: Decimal
    status: str
    valor_contado: Decimal | None = None
    observacoes: str | None = None
    valor_guardado: Decimal | None = None
    valor_retirado: Decimal | None = None
    usuario_id: int | None = None
    usuario_nome: str | None = None  # so' no /historico
    vencido: bool = False  # aberto ha mais de 24h: so' deixa fechar


class ResumoCaixaResponse(Schema):
    saldo_inicial: Decimal
    vendas_dinheiro: Decimal
    vendas_pix: Decimal
    vendas_cartao: Decimal
    vendas_prazo: Decimal
    suprimentos: Decimal
    sangrias: Decimal
    recebimentos_fiado: Decimal
    # fiado recebido separado por forma (outros = transferencia etc.)
    recebimentos_fiado_dinheiro: Decimal = Decimal("0")
    recebimentos_fiado_pix: Decimal = Decimal("0")
    recebimentos_fiado_cartao: Decimal = Decimal("0")
    recebimentos_fiado_outros: Decimal = Decimal("0")
    # so caixas antigos: boleto pago em dinheiro que saiu da gaveta
    contas_pagas_caixa: Decimal = Decimal("0")
    total_previsto: Decimal
    total_geral: Decimal


class EntradasCaixaResponse(Schema):
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
    contas_pagas_por_forma: dict[str, Decimal] = {}
    sobrou: Decimal  # total - contas_pagas - sangrias
