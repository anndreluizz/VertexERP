
from app.schemas.base import Schema


class PerfilCreate(Schema):
    nome: str
    permissoes: list[str] = []


class PerfilUpdate(Schema):
    nome: str
    permissoes: list[str] = []


class PerfilResponse(Schema):
    id: int
    nome: str
    permissoes: list[str]
