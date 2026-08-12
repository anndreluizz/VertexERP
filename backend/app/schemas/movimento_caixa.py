from datetime import datetime

from pydantic import BaseModel


class MovimentoCaixaBase(BaseModel):
    tipo: str
    descricao: str | None = None
    valor: float


class MovimentoCaixaCreate(MovimentoCaixaBase):
    pass


class MovimentoCaixaResponse(MovimentoCaixaBase):
    id: int
    caixa_id: int
    usuario_id: int
    venda_id: int | None = None
    data: datetime

    class Config:
        orm_mode = True