
from app.schemas.base import Schema


class PlanoContaCreate(Schema):
    codigo: str | None = None
    nome: str
    tipo: str
    conta_pai_id: int | None = None


class PlanoContaUpdate(Schema):
    codigo: str | None = None
    nome: str
    tipo: str
    conta_pai_id: int | None = None
    ativo: bool = True


class PlanoContaResponse(Schema):
    id: int
    codigo: str | None = None
    nome: str
    tipo: str
    conta_pai_id: int | None = None
    conta_pai_nome: str | None = None
    ativo: bool
