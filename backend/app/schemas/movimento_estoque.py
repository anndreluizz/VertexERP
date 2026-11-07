from datetime import datetime

from app.schemas.base import Quantidade, Schema


class MovimentoEstoqueBase(Schema):
    produto_id: int
    tipo: str
    quantidade: Quantidade
    motivo: str | None = None


class MovimentoEstoqueCreate(MovimentoEstoqueBase):
    pass


class MovimentoEstoqueResponse(MovimentoEstoqueBase):
    id: int
    usuario_id: int
    transferencia_id: int | None = None
    data: datetime
