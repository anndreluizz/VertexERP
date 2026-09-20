from datetime import datetime

from pydantic import BaseModel


class ItemContagemEstoqueResponse(BaseModel):
    id: int
    produto_id: int
    produto_nome: str | None = None
    quantidade_sistema: int
    quantidade_contada: int | None = None

    class Config:
        orm_mode = True


class ItemContagemEstoqueUpdate(BaseModel):
    quantidade_contada: int


class ContagemEstoqueCreate(BaseModel):
    observacao: str | None = None


class ContagemEstoqueResponse(BaseModel):
    id: int
    loja_id: int
    usuario_id: int
    status: str
    observacao: str | None = None
    criado_em: datetime
    finalizado_em: datetime | None = None
    itens: list[ItemContagemEstoqueResponse] = []

    class Config:
        orm_mode = True
