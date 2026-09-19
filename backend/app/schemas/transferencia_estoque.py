from datetime import datetime

from pydantic import BaseModel


class TransferenciaEstoqueCreate(BaseModel):
    produto_id: int
    loja_destino_id: int
    quantidade: int
    motivo: str | None = None


class TransferenciaEstoqueResponse(BaseModel):
    id: int
    produto_id: int
    loja_origem_id: int
    loja_destino_id: int
    quantidade: int
    usuario_id: int
    motivo: str | None
    data: datetime

    class Config:
        orm_mode = True
