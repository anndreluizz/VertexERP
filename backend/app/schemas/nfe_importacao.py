from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.enums.forma_pagamento import FormaPagamento


# ==========================================
# PREVIEW (POST /fornecedores/importar-nfe)
# ==========================================

class NFeImportarRequest(BaseModel):
    xml_conteudo: str


class FornecedorPreviewResponse(BaseModel):
    encontrado: bool
    id: int | None = None
    cnpj: str
    razao_social: str
    nome_fantasia: str | None = None
    margem_padrao: Decimal = Decimal("0")


class ItemPreviewResponse(BaseModel):
    codigo: str
    descricao: str
    codigo_barras: str | None = None
    quantidade: int
    custo: Decimal
    produto_id: int | None = None
    preco_atual: Decimal | None = None
    preco_sugerido: Decimal


class NFePreviewResponse(BaseModel):
    fornecedor: FornecedorPreviewResponse
    itens: list[ItemPreviewResponse]


# ==========================================
# CONFIRMACAO (POST /compras/importar-nfe)
# ==========================================

class FornecedorNovoRequest(BaseModel):
    razao_social: str
    nome_fantasia: str | None = None
    cnpj: str
    margem_padrao: Decimal = Decimal("0")


class ItemImportacaoRequest(BaseModel):
    produto_id: int | None = None
    codigo: str
    descricao: str
    codigo_barras: str | None = None
    quantidade: int
    custo: Decimal
    preco_venda: Decimal


class ImportarNFeConfirmarRequest(BaseModel):
    fornecedor_id: int | None = None
    fornecedor_novo: FornecedorNovoRequest | None = None
    forma_pagamento: FormaPagamento
    data_vencimento: datetime | None = None
    observacao: str | None = None
    itens: list[ItemImportacaoRequest]
