
from app.schemas.base import Quantidade, Schema


class KitItemCreate(Schema):
    produto_componente_id: int
    quantidade: Quantidade = 1


class KitItemResponse(Schema):
    id: int
    kit_id: int
    produto_componente_id: int
    produto_componente_nome: str | None = None
    quantidade: Quantidade
