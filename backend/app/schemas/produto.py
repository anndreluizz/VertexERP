from decimal import Decimal
from pydantic import BaseModel


class ProdutoBase(BaseModel):
    codigo: str
    nome: str
    descricao: str | None = None
    codigo_barras: str | None = None
    categoria: str | None = None
    unidade: str = "UN"
    preco_custo: Decimal = Decimal("0.00")
    preco_venda: Decimal = Decimal("0.00")
    estoque: int = 0
    estoque_minimo: int = 0


class ProdutoCreate(ProdutoBase):
    pass


class ProdutoUpdate(ProdutoBase):
    ativo: bool = True


class ProdutoResponse(ProdutoBase):
    id: int
    ativo: bool

    class Config:
        orm_mode = True