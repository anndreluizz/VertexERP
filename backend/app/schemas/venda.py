from datetime import datetime
from decimal import Decimal
from app.enums.forma_pagamento import FormaPagamento
from pydantic import BaseModel


class ItemVendaCreate(BaseModel):
    produto_id: int
    quantidade: int
    valor_unitario: Decimal


class ItemVendaResponse(BaseModel):
    id: int
    produto_id: int
    quantidade: int
    valor_unitario: Decimal
    subtotal: Decimal

    class Config:
        orm_mode = True


class VendaCreate(BaseModel):
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

    itens: list[ItemVendaCreate]


class VendaResponse(BaseModel):
    id: int

    cliente_id: int | None

    usuario_id: int | None = None

    usuario_nome: str | None = None

    lucro: Decimal | None = None

    data: datetime

    valor_total: Decimal

    desconto: Decimal

    observacao: str | None

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

    class Config:
        orm_mode = True


class ComprovanteEnvioCreate(BaseModel):
    canal: str  # WHATSAPP ou EMAIL
    destino: str
    status: str  # ENVIADO ou FALHOU
    erro: str | None = None


class ComprovanteEnviarWhatsappRequest(BaseModel):
    pdf_base64: str
    nome_arquivo: str = "comprovante.pdf"
    legenda: str = ""


class ComprovanteEnviarEmailRequest(BaseModel):
    pdf_base64: str
    destinatario: str | None = None
    nome_arquivo: str = "comprovante.pdf"
    assunto: str = "Comprovante da sua compra"
    corpo: str = ""


class ComprovanteEnvioResponse(BaseModel):
    id: int
    canal: str
    destino: str
    status: str
    erro: str | None
    usuario_id: int | None
    usuario_nome: str | None
    data: datetime

    class Config:
        orm_mode = True


class ComprovanteItemResponse(BaseModel):
    produto_id: int
    nome: str
    quantidade: int
    valor_unitario: Decimal
    subtotal: Decimal


class ComprovanteVendaResponse(BaseModel):
    """Tudo que o comprovante de uma venda precisa numa unica chamada
    -- evita o frontend combinar varias requisicoes (venda + cliente +
    saldo devedor + nome dos produtos) so pra montar o PDF."""

    venda_id: int
    data: datetime
    usuario_nome: str | None
    cliente_id: int | None
    cliente_nome: str | None
    cliente_cpf_cnpj: str | None
    cliente_telefone: str | None
    cliente_email: str | None
    itens: list[ComprovanteItemResponse]
    desconto: Decimal
    valor_total: Decimal
    forma_pagamento: str
    forma_pagamento_2: str | None = None
    valor_forma_2: Decimal | None = None
    observacao: str | None
    situacao: str  # PAGO ou FIADO
    saldo_devedor_cliente: Decimal | None = None