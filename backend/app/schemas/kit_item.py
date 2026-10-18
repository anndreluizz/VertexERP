
from app.schemas.base import Schema


class KitItemCreate(Schema):
    produto_componente_id: int
    quantidade: int = 1


class KitItemResponse(Schema):
    id: int
    kit_id: int
    produto_componente_id: int
    produto_componente_nome: str | None = None
    quantidade: int
