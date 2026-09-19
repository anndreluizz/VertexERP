from decimal import Decimal

from pydantic import BaseModel


class FornecedorCreate(BaseModel):
    razao_social: str
    nome_fantasia: str | None = None
    cnpj: str
    email: str | None = None
    telefone: str | None = None
    cidade: str | None = None
    estado: str | None = None
    margem_padrao: Decimal = Decimal("0")


class FornecedorUpdate(BaseModel):
    razao_social: str
    nome_fantasia: str | None = None
    cnpj: str
    email: str | None = None
    telefone: str | None = None
    cidade: str | None = None
    estado: str | None = None
    margem_padrao: Decimal = Decimal("0")
    ativo: bool


class FornecedorResponse(BaseModel):
    id: int
    razao_social: str
    nome_fantasia: str | None
    cnpj: str
    email: str | None
    telefone: str | None
    cidade: str | None
    estado: str | None
    margem_padrao: Decimal
    ativo: bool

    class Config:
        orm_mode = True
