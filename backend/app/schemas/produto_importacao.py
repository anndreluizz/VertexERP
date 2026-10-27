from decimal import Decimal

from app.schemas.base import Quantidade, Schema


class ImportarCsvRequest(Schema):
    csv_conteudo: str


class ItemImportacaoPreview(Schema):
    linha: int
    codigo: str
    nome: str
    categoria: str | None = None
    codigo_barras: str | None = None
    preco_custo: Decimal
    preco_venda: Decimal
    estoque: Quantidade
    estoque_minimo: Quantidade
    unidade: str
    produto_id: int | None = None  # preenchido = vai ATUALIZAR, nao criar
    erro: str | None = None


class PreviewImportacaoResponse(Schema):
    itens: list[ItemImportacaoPreview]
    total_novos: int
    total_atualizados: int
    total_com_erro: int


class ItemImportacaoConfirmar(Schema):
    codigo: str
    nome: str
    categoria: str | None = None
    codigo_barras: str | None = None
    preco_custo: Decimal
    preco_venda: Decimal
    estoque: Quantidade
    estoque_minimo: Quantidade
    unidade: str
    produto_id: int | None = None


class ConfirmarImportacaoRequest(Schema):
    itens: list[ItemImportacaoConfirmar]


class ConfirmarImportacaoResponse(Schema):
    criados: int
    atualizados: int
