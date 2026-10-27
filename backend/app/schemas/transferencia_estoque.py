from datetime import datetime

from app.schemas.base import Quantidade, Schema


class TransferenciaEstoqueCreate(Schema):
    produto_id: int
    loja_destino_id: int
    quantidade: Quantidade
    motivo: str | None = None


class TransferenciaEstoqueResponse(Schema):
    id: int
    produto_id: int
    loja_origem_id: int
    loja_destino_id: int
    quantidade: Quantidade
    usuario_id: int
    motivo: str | None = None
    data: datetime
