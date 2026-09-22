from decimal import Decimal

from pydantic import BaseModel


class ImportarCsvRequest(BaseModel):
    csv_conteudo: str


class ItemImportacaoPreview(BaseModel):
    linha: int
    codigo: str
    nome: str
    categoria: str | None = None
    codigo_barras: str | None = None
    preco_custo: Decimal
    preco_venda: Decimal
    estoque: int
    estoque_minimo: int
    unidade: str
    produto_id: int | None = None  # preenchido = vai ATUALIZAR, nao criar
    erro: str | None = None


class PreviewImportacaoResponse(BaseModel):
    itens: list[ItemImportacaoPreview]
    total_novos: int
    total_atualizados: int
    total_com_erro: int


class ItemImportacaoConfirmar(BaseModel):
    codigo: str
    nome: str
    categoria: str | None = None
    codigo_barras: str | None = None
    preco_custo: Decimal
    preco_venda: Decimal
    estoque: int
    estoque_minimo: int
    unidade: str
    produto_id: int | None = None


class ConfirmarImportacaoRequest(BaseModel):
    itens: list[ItemImportacaoConfirmar]


class ConfirmarImportacaoResponse(BaseModel):
    criados: int
    atualizados: int
