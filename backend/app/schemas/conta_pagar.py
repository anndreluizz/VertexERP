from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, condecimal, conint, constr


class ContaPagarBase(BaseModel):
    data_vencimento: datetime
    valor: Decimal
    descricao: str | None = None
    categoria: str | None = None
    centro_custo: str | None = None
    plano_conta_id: int | None = None
    observacao: str | None = None
    numero_boleto: str | None = None


class ContaPagarCreate(ContaPagarBase):
    # CNPJ do beneficiario lido do PDF do boleto -- nao fica na conta,
    # so' ensina o sistema o nome desse fornecedor (ver
    # BeneficiarioBoletoService.aprender)
    beneficiario_cnpj: str | None = None

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
    plano_conta_id: int | None = None
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

    plano_conta_id: int | None = None

    plano_conta_nome: str | None = None

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

    recorrente_id: int | None = None

    valor_a_confirmar: bool = False

    parcelamento_id: str | None = None

    parcela_numero: int | None = None

    parcela_total: int | None = None

    class Config:
        orm_mode = True


class ContaPagarParceladaCreate(ContaPagarCreate):
    """Boleto parcelado: 'valor' e o valor de UMA parcela e
    data_vencimento o da primeira; as outras vencem no mesmo dia dos
    meses seguintes (ver ContaPagarService.criar_parcelado)."""
    numero_parcelas: conint(ge=2, le=60)
    # MENSAL = mesmo dia todo mes; 30_DIAS = de 30 em 30 dias
    intervalo: str = "MENSAL"
    # datas escolhidas na tela, uma por parcela (sobrepoe o intervalo)
    vencimentos: list[date] | None = None


class ContaRecorrenteCreate(BaseModel):
    descricao: constr(min_length=1, max_length=110)
    valor: condecimal(gt=0, decimal_places=2)
    # o dia deste vencimento vira o dia de todo mes
    primeiro_vencimento: date
    valor_variavel: bool = False
    categoria: str | None = None
    centro_custo: str | None = None
    plano_conta_id: int | None = None
    observacao: str | None = None
    # emprestimo/financiamento: quantos meses no total (None = sempre)
    meses: conint(ge=1, le=360) | None = None
    # boleto/PDF do 1o mes (vao so' na conta desse mes)
    numero_boleto: str | None = None
    beneficiario_cnpj: str | None = None
    documento_base64: str | None = None
    documento_nome: str | None = None
    documento_tipo: str | None = None


class ContaRecorrenteUpdate(BaseModel):
    descricao: constr(min_length=1, max_length=110) | None = None
    valor: condecimal(gt=0, decimal_places=2) | None = None
    dia_vencimento: conint(ge=1, le=31) | None = None
    valor_variavel: bool | None = None
    categoria: str | None = None
    centro_custo: str | None = None


class ContaRecorrenteResponse(BaseModel):
    id: int
    descricao: str
    valor: Decimal
    dia_vencimento: int
    valor_variavel: bool
    categoria: str | None = None
    centro_custo: str | None = None
    ativa: bool
    ultima_competencia: date | None = None
    fim_competencia: date | None = None

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


class LerBoletoRequest(BaseModel):
    """Um dos dois: o código (linha digitável/código de barras, bipado
    ou digitado) ou o PDF do boleto em base64."""
    codigo: str | None = None
    pdf_base64: str | None = None


class BoletoJaLancado(BaseModel):
    id: int
    descricao: str | None = None
    status: str
    valor: Decimal


class ParcelaSugerida(BaseModel):
    id: int
    descricao: str | None = None
    parcela_numero: int | None = None
    parcela_total: int | None = None
    valor: Decimal
    data_vencimento: datetime


class LerBoletoResponse(BaseModel):
    tipo: str | None = None
    linha_digitavel: str | None = None
    codigo_barras: str | None = None
    banco_codigo: str | None = None
    banco_nome: str | None = None
    valor: Decimal | None = None
    vencimento: date | None = None
    segmento: str | None = None
    beneficiario_nome: str | None = None
    beneficiario_cnpj: str | None = None
    # nome que o sistema aprendeu pra esse beneficiario (ou o do PDF)
    fornecedor_sugerido: str | None = None
    categoria_sugerida: str | None = None
    ja_lancado: BoletoJaLancado | None = None
    # parcela em aberto sem codigo que esse boleto paga (mesmo valor,
    # vencimento perto): guardar o codigo nela em vez de lancar outra
    parcela_sugerida: ParcelaSugerida | None = None
