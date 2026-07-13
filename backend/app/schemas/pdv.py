from decimal import Decimal

from pydantic import BaseModel


class ProdutoPDV(BaseModel):
    id: int
    codigo: str
    codigo_barras: str | None = None
    nome: str
    preco: Decimal
    estoque: int