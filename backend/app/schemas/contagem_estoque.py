from datetime import datetime

from app.schemas.base import Schema


class ItemContagemEstoqueResponse(Schema):
    id: int
    produto_id: int
    produto_nome: str | None = None
    quantidade_sistema: int
    quantidade_contada: int | None = None


class ItemContagemEstoqueUpdate(Schema):
    quantidade_contada: int


class ContagemEstoqueCreate(Schema):
    observacao: str | None = None


class ContagemEstoqueResponse(Schema):
    id: int
    loja_id: int
    usuario_id: int
    status: str
    observacao: str | None = None
    criado_em: datetime
    finalizado_em: datetime | None = None
    itens: list[ItemContagemEstoqueResponse] = []
