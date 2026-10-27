from datetime import date
from decimal import Decimal

from app.schemas.base import Quantidade, Schema


class ProdutoBase(Schema):
    codigo: str
    nome: str
    descricao: str | None = None
    codigo_barras: str | None = None
    categoria: str | None = None
    marca_id: int | None = None
    colecao: str | None = None
    cor: str | None = None
    tamanho: str | None = None
    produto_pai_id: int | None = None
    unidade: str = "UN"
    preco_custo: Decimal = Decimal("0.00")
    preco_venda: Decimal = Decimal("0.00")
    preco_promocional: Decimal | None = None
    promocao_inicio: date | None = None
    promocao_fim: date | None = None
    estoque: Quantidade = 0
    estoque_minimo: Quantidade = 0
    favorito: bool = False
    eh_kit: bool = False

    # imagem em base64 (entrada apenas); None mantem a foto atual
    foto_base64: str | None = None


class ProdutoCreate(ProdutoBase):
    codigo: str = ""  # vazio = proximo codigo interno (0001, 0002...)


class ProdutoUpdate(ProdutoBase):
    ativo: bool = True


class ProdutoResponse(Schema):
    id: int
    loja_id: int | None = None
    # so' vem False na listagem por loja (?loja_id=): produto que so'
    # outra loja tem; a tela de Produtos esconde por padrao
    na_loja: bool = True
    codigo: str
    nome: str
    descricao: str | None = None
    codigo_barras: str | None = None
    categoria: str | None = None
    marca_id: int | None = None
    colecao: str | None = None
    cor: str | None = None
    tamanho: str | None = None
    produto_pai_id: int | None = None
    unidade: str = "UN"
    preco_custo: Decimal
    preco_venda: Decimal
    preco_promocional: Decimal | None = None
    promocao_inicio: date | None = None
    promocao_fim: date | None = None
    preco_efetivo: Decimal
    em_promocao: bool = False
    estoque: Quantidade
    estoque_minimo: Quantidade
    ativo: bool
    favorito: bool = False
    eh_kit: bool = False
    tem_foto: bool = False


class ProdutoFotoCreate(Schema):
    imagem_base64: str
    principal: bool = False


class ProdutoFotoResponse(Schema):
    id: int
    produto_id: int
    ordem: int
    principal: bool
