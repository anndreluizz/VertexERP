from decimal import Decimal
from pydantic import BaseModel


class ProdutoBase(BaseModel):
    codigo: str
    nome: str
    descricao: str | None = None
    codigo_barras: str | None = None
    categoria: str | None = None
    marca_id: int | None = None
    colecao: str | None = None
    unidade: str = "UN"
    preco_custo: Decimal = Decimal("0.00")
    preco_venda: Decimal = Decimal("0.00")
    estoque: int = 0
    estoque_minimo: int = 0
    favorito: bool = False

    # imagem em base64 (entrada apenas); None mantem a foto atual
    foto_base64: str | None = None


class ProdutoCreate(ProdutoBase):
    pass


class ProdutoUpdate(ProdutoBase):
    ativo: bool = True


class ProdutoResponse(BaseModel):
    id: int
    loja_id: int | None = None
    codigo: str
    nome: str
    descricao: str | None = None
    codigo_barras: str | None = None
    categoria: str | None = None
    marca_id: int | None = None
    colecao: str | None = None
    unidade: str = "UN"
    preco_custo: Decimal
    preco_venda: Decimal
    estoque: int
    estoque_minimo: int
    ativo: bool
    favorito: bool = False
    tem_foto: bool = False

    class Config:
        orm_mode = True


class ProdutoFotoCreate(BaseModel):
    imagem_base64: str
    principal: bool = False


class ProdutoFotoResponse(BaseModel):
    id: int
    produto_id: int
    ordem: int
    principal: bool

    class Config:
        orm_mode = True
