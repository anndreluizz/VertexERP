from datetime import datetime

from pydantic import BaseModel

from app.enums.tipo_movimento_estoque import TipoMovimentoEstoque


class MovimentoEstoqueCreate(BaseModel):
    produto_id: int
    tipo: TipoMovimentoEstoque
    quantidade: int
    motivo: str | None = None


class MovimentoEstoqueResponse(BaseModel):
    id: int
    produto_id: int
    usuario_id: int
    tipo: TipoMovimentoEstoque
    quantidade: int
    motivo: str | None
    data: datetime

    class Config:
        orm_mode = True
