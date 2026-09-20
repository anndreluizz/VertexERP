from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ContaPagarBase(BaseModel):
    data_vencimento: datetime
    valor: Decimal
    descricao: str | None = None
    categoria: str | None = None
    centro_custo: str | None = None
    observacao: str | None = None
    numero_boleto: str | None = None


class ContaPagarCreate(ContaPagarBase):
    # imagem/PDF em base64 (entrada apenas) -- mesmo padrao do
    # foto_base64 do Cliente. None/ausente = sem documento anexado.
    documento_base64: str | None = None
    documento_nome: str | None = None
    documento_tipo: str | None = None


class ContaPagarUpdate(BaseModel):
    data_vencimento: datetime | None = None
    valor: Decimal | None = None
    descricao: str | None = None
    categoria: str | None = None
    centro_custo: str | None = None
    observacao: str | None = None
    numero_boleto: str | None = None
    status: str | None = None
    # None/ausente mantem o documento atual -- so troca quando vier
    # preenchido (ver ContaPagarService.atualizar)
    documento_base64: str | None = None
    documento_nome: str | None = None
    documento_tipo: str | None = None


class ContaPagarResponse(BaseModel):
    id: int

    data_emissao: datetime

    data_vencimento: datetime

    data_pagamento: datetime | None

    valor: Decimal

    descricao: str | None

    categoria: str | None

    centro_custo: str | None = None

    observacao: str | None

    numero_boleto: str | None

    status: str

    tem_documento: bool = False

    documento_nome: str | None = None

    tem_comprovante_pagamento: bool = False

    comprovante_pagamento_nome: str | None = None

    forma_pagamento: str | None = None

    banco_pagamento: str | None = None

    numero_transacao: str | None = None

    class Config:
        orm_mode = True


class PagarContaSchema(BaseModel):
    # como o pagamento foi feito -- PIX/TRANSFERENCIA/DINHEIRO/CARTAO/
    # BOLETO, mesmos valores de Venda.forma_pagamento.
    forma_pagamento: str | None = None
    banco_pagamento: str | None = None
    numero_transacao: str | None = None
    # comprovante do pagamento (print de PIX, transferencia etc.) --
    # opcional, mesmo padrao base64 do documento/boleto.
    comprovante_base64: str | None = None
    comprovante_nome: str | None = None
    comprovante_tipo: str | None = None
    # de onde veio a acao -- so pra linha do tempo (ver
    # ContaPagarEvento); nao afeta nenhuma regra de negocio.
    dispositivo: str | None = None


class TrocarComprovanteSchema(BaseModel):
    # troca o comprovante de uma despesa ja paga -- diferente do
    # PagarContaSchema porque aqui o comprovante e obrigatorio (nao faz
    # sentido "trocar" por nada).
    comprovante_base64: str
    comprovante_nome: str | None = None
    comprovante_tipo: str | None = None
    dispositivo: str | None = None


class ContaPagarEventoResponse(BaseModel):
    id: int
    tipo: str
    usuario_id: int | None = None
    usuario_nome: str | None = None
    dispositivo: str | None = None
    detalhes: str | None = None
    data: datetime

    class Config:
        orm_mode = True
