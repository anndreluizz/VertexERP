from decimal import Decimal

from app.schemas.base import Schema


class ProdutoPDV(Schema):
    id: int
    codigo: str
    codigo_barras: str | None = None
    nome: str
    preco: Decimal
    estoque: int
    tem_foto: bool = False
    favorito: bool = False