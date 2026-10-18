from datetime import date, datetime
from decimal import Decimal

from pydantic import EmailStr, Field

from app.schemas.base import Schema
from app.schemas.movimento_fiado import MovimentoFiadoResponse


class ClienteCreate(Schema):
    nome: str
    cpf_cnpj: str | None = None
    email: EmailStr | None = None
    telefone: str | None = None
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    data_nascimento: date | None = None
    limite_credito: Decimal | None = None

    # imagem em base64 (entrada apenas); None mantem a foto atual
    foto_base64: str | None = None


class ClienteUpdate(Schema):
    nome: str
    cpf_cnpj: str | None = None
    email: EmailStr | None = None
    telefone: str | None = None
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    ativo: bool
    data_nascimento: date | None = None
    limite_credito: Decimal | None = None

    foto_base64: str | None = None


class ClienteResponse(Schema):
    id: int
    loja_id: int | None = None
    nome: str
    cpf_cnpj: str | None = None
    email: EmailStr | None = None
    telefone: str | None = None
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    ativo: bool
    criado_em: datetime
    data_nascimento: date | None = None
    limite_credito: Decimal | None = None
    tem_foto: bool = False
    negativado: bool = False
    negativado_em: datetime | None = None
    negativado_motivo: str | None = None


class ClienteEnviarWhatsappRequest(Schema):
    texto: str


class ClienteObservacaoCreate(Schema):
    texto: str


class ClienteObservacaoResponse(Schema):
    id: int
    cliente_id: int
    usuario_id: int
    texto: str
    criado_em: datetime


# ==================================================
# LGPD -- direito de acesso (exportar) e ao esquecimento (anonimizar)
# ==================================================


class VendaResumoLgpdResponse(Schema):
    """Só o essencial de cada venda pro relatório de dados pessoais --
    não é a venda completa (ver VendaResponse em schemas/venda.py),
    só o suficiente pra mostrar que a venda existe e seus valores."""

    id: int
    data: datetime
    valor_total: Decimal
    forma_pagamento: str
    status: str


class ClienteDadosLgpdResponse(Schema):
    """Todos os dados pessoais guardados sobre um cliente, numa
    chamada só -- atende o direito de acesso/portabilidade da LGPD
    (Lei 13.709/2018, art. 18, II). Ver ClienteService.exportar_dados_lgpd."""

    cliente_id: int
    nome: str
    cpf_cnpj: str | None = None
    telefone: str | None = None
    email: EmailStr | None = None
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    data_nascimento: date | None = None
    limite_credito: Decimal | None = None
    tem_foto: bool
    cadastrado_em: datetime

    saldo_devedor_fiado: Decimal
    movimentos_fiado: list[MovimentoFiadoResponse]
    vendas: list[VendaResumoLgpdResponse]
    observacoes: list[ClienteObservacaoResponse]


class ClienteAnonimizadoResponse(Schema):
    cliente_id: int
    mensagem: str


class NegativarClienteRequest(Schema):
    motivo: str = Field(min_length=1, max_length=200)
