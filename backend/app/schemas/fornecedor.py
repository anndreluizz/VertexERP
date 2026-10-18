from decimal import Decimal

from app.schemas.base import Schema


class FornecedorCreate(Schema):
    razao_social: str
    nome_fantasia: str | None = None
    cnpj: str
    email: str | None = None
    telefone: str | None = None
    cidade: str | None = None
    estado: str | None = None
    margem_padrao: Decimal = Decimal("0")


class FornecedorUpdate(Schema):
    razao_social: str
    nome_fantasia: str | None = None
    cnpj: str
    email: str | None = None
    telefone: str | None = None
    cidade: str | None = None
    estado: str | None = None
    margem_padrao: Decimal = Decimal("0")
    ativo: bool


class FornecedorResponse(Schema):
    id: int
    razao_social: str
    nome_fantasia: str | None = None
    cnpj: str
    email: str | None = None
    telefone: str | None = None
    cidade: str | None = None
    estado: str | None = None
    margem_padrao: Decimal
    ativo: bool
