from decimal import Decimal

from app.schemas.base import Quantidade, Schema


class ProdutoPDV(Schema):
    id: int
    codigo: str
    codigo_barras: str | None = None
    nome: str
    preco: Decimal
    estoque: Quantidade
    tem_foto: bool = False
    favorito: bool = False
    unidade: str = "UN"