from pydantic import BaseModel


class FornecedorCreate(BaseModel):
    razao_social: str
    nome_fantasia: str | None = None
    cnpj: str
    email: str | None = None
    telefone: str | None = None
    cidade: str | None = None
    estado: str | None = None


class FornecedorUpdate(BaseModel):
    razao_social: str
    nome_fantasia: str | None = None
    cnpj: str
    email: str | None = None
    telefone: str | None = None
    cidade: str | None = None
    estado: str | None = None
    ativo: bool


class FornecedorResponse(BaseModel):
    id: int
    razao_social: str
    nome_fantasia: str | None
    cnpj: str
    email: str |None
    telefone: str | None
    cidade: str | None
    estado: str | None
    ativo: bool

    class Config:
        orm_mode = True