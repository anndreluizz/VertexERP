from datetime import datetime
from decimal import Decimal
from app.enums.forma_pagamento import FormaPagamento
from pydantic import condecimal, constr

from app.schemas.base import Quantidade, QuantidadePositiva, Schema


class ItemVendaCreate(Schema):
    produto_id: int
    # quantidade <= 0 passava na checagem de estoque e SOMAVA estoque
    # (devolucao disfarcada de venda, sem passar pelo cancelamento)
    quantidade: QuantidadePositiva
    valor_unitario: condecimal(ge=0, decimal_places=2)


class ItemVendaResponse(Schema):
    id: int
    produto_id: int
    produto_nome: str | None = None
    quantidade: Quantidade
    unidade: str = "UN"
    valor_unitario: Decimal
    subtotal: Decimal


class VendaCreate(Schema):
    cliente_id: int | None = None

    observacao: str | None = None

    desconto: Decimal = Decimal("0.00")

    # AVISTA, PIX, DEBITO, CREDITO, BOLETO, PRAZO
    forma_pagamento: FormaPagamento = FormaPagamento.DINHEIRO

    # pagamento dividido (opcional, no maximo 2 formas): valor_forma_2
    # cobre parte do total nessa segunda forma, o restante fica na
    # forma_pagamento principal
    forma_pagamento_2: FormaPagamento | None = None
    valor_forma_2: Decimal | None = None

    data_vencimento: datetime | None = None

    # opcional: mesmo valor em dois envios = mesma venda (ver
    # VendaService.criar). O PDV gera uma por carrinho.
    chave_idempotencia: constr(min_length=8, max_length=64) | None = None

    itens: list[ItemVendaCreate]


class VendaSuspensaCreate(Schema):
    """Carrinho salvo pra retomar depois (status=ABERTA) -- sem forma
    de pagamento, sem data de vencimento: nada disso foi decidido
    ainda, a venda so vira de verdade quando for retomada e finalizada
    via POST /vendas/ normal."""

    cliente_id: int | None = None

    desconto: Decimal = Decimal("0.00")

    itens: list[ItemVendaCreate]


class ItemVendaSuspensaResponse(Schema):
    produto_id: int
    codigo: str | None = None
    nome: str
    quantidade: Quantidade
    valor_unitario: Decimal
    estoque: Quantidade | None = None
    unidade: str | None = "UN"


class VendaSuspensaResponse(Schema):
    """Mesma ideia de VendaResponse, mas com nome/codigo/estoque atual
    do produto já embutidos em cada item -- pra tela de PDV conseguir
    repopular o carrinho ao retomar sem precisar de uma chamada extra
    por produto."""

    id: int
    cliente_id: int | None = None
    cliente_nome: str | None = None
    data: datetime
    desconto: Decimal
    itens: list[ItemVendaSuspensaResponse]


class VendaResponse(Schema):
    id: int

    loja_id: int | None = None

    cliente_id: int | None = None
    cliente_nome: str | None = None

    usuario_id: int | None = None

    usuario_nome: str | None = None

    lucro: Decimal | None = None

    data: datetime

    valor_total: Decimal

    desconto: Decimal

    observacao: str | None = None
    status: str

    forma_pagamento: FormaPagamento

    forma_pagamento_2: FormaPagamento | None = None
    valor_forma_2: Decimal | None = None

    data_vencimento: datetime | None = None

    cancelado_em: datetime | None = None
    cancelado_por_id: int | None = None
    cancelado_por_nome: str | None = None
    motivo_cancelamento: str | None = None

    itens: list[ItemVendaResponse]


class ComprovanteEnvioCreate(Schema):
    canal: str  # WHATSAPP ou EMAIL
    destino: str
    status: str  # ENVIADO ou FALHOU
    erro: str | None = None


class ComprovanteEnviarWhatsappRequest(Schema):
    pdf_base64: str
    nome_arquivo: str = "comprovante.pdf"
    legenda: str = ""


class ComprovanteEnviarEmailRequest(Schema):
    pdf_base64: str
    destinatario: str | None = None
    nome_arquivo: str = "comprovante.pdf"
    assunto: str = "Comprovante da sua compra"
    corpo: str = ""


class ComprovanteEnvioResponse(Schema):
    id: int
    canal: str
    destino: str
    status: str
    erro: str | None = None
    usuario_id: int | None = None
    usuario_nome: str | None = None
    data: datetime


class ComprovanteItemResponse(Schema):
    produto_id: int
    nome: str
    quantidade: Quantidade
    unidade: str | None = "UN"
    valor_unitario: Decimal
    subtotal: Decimal


class ComprovanteVendaResponse(Schema):
    """Tudo que o comprovante de uma venda precisa numa unica chamada
    -- evita o frontend combinar varias requisicoes (venda + cliente +
    saldo devedor + nome dos produtos) so pra montar o PDF."""

    venda_id: int
    data: datetime
    usuario_nome: str | None = None
    cliente_id: int | None = None
    cliente_nome: str | None = None
    cliente_cpf_cnpj: str | None = None
    cliente_telefone: str | None = None
    cliente_email: str | None = None
    itens: list[ComprovanteItemResponse]
    desconto: Decimal
    valor_total: Decimal
    forma_pagamento: str
    forma_pagamento_2: str | None = None
    valor_forma_2: Decimal | None = None
    observacao: str | None = None
    situacao: str  # PAGO ou FIADO
    saldo_devedor_cliente: Decimal | None = None


class ResumoVendedorItem(Schema):
    """Total vendido por usuário (vendedora) num período -- ver
    GET /vendas/resumo-vendedores."""
    usuario_id: int | None = None
    usuario_nome: str | None = None
    quantidade_vendas: int
    total_vendido: Decimal
    total_devolvido: Decimal
    total_liquido: Decimal
