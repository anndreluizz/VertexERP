from datetime import datetime
from decimal import Decimal

from app.schemas.base import Schema
from app.enums.forma_pagamento import FormaPagamento


# ==========================================
# PREVIEW (POST /fornecedores/importar-nfe)
# ==========================================

class NFeImportarRequest(Schema):
    xml_conteudo: str


class FornecedorPreviewResponse(Schema):
    encontrado: bool
    id: int | None = None
    cnpj: str
    razao_social: str
    nome_fantasia: str | None = None
    margem_padrao: Decimal = Decimal("0")


class ItemPreviewResponse(Schema):
    codigo: str
    descricao: str
    codigo_barras: str | None = None
    quantidade: int
    custo: Decimal
    produto_id: int | None = None
    preco_atual: Decimal | None = None
    preco_sugerido: Decimal


class NFePreviewResponse(Schema):
    fornecedor: FornecedorPreviewResponse
    itens: list[ItemPreviewResponse]


# ==========================================
# CONFIRMACAO (POST /compras/importar-nfe)
# ==========================================

class FornecedorNovoRequest(Schema):
    razao_social: str
    nome_fantasia: str | None = None
    cnpj: str
    margem_padrao: Decimal = Decimal("0")


class ItemImportacaoRequest(Schema):
    produto_id: int | None = None
    codigo: str
    descricao: str
    codigo_barras: str | None = None
    quantidade: int
    custo: Decimal
    preco_venda: Decimal
    # so' vale pra produto ja cadastrado: sem isso o preco de venda
    # atual da loja fica como esta (o custo e' atualizado sempre).
    # Antes o preco vinha sempre de custo x margem -- com margem 0% a
    # importacao derrubava o preco de venda pro preco de custo.
    atualizar_preco_venda: bool = False


class ImportarNFeConfirmarRequest(Schema):
    fornecedor_id: int | None = None
    fornecedor_novo: FornecedorNovoRequest | None = None
    forma_pagamento: FormaPagamento
    data_vencimento: datetime | None = None
    numero_parcelas: int = 1
    observacao: str | None = None
    itens: list[ItemImportacaoRequest]
