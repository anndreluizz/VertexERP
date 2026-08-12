from datetime import datetime

from pydantic import BaseModel


class MovimentoEstoqueBase(BaseModel):
    produto_id: int
    tipo: str
    quantidade: int
    motivo: str | None = None


class MovimentoEstoqueCreate(MovimentoEstoqueBase):
    pass


class MovimentoEstoqueResponse(MovimentoEstoqueBase):
    id: int
    usuario_id: int
    data: datetime

    class Config:
        orm_mode = True
