from pydantic import BaseModel, EmailStr


class ClienteCreate(BaseModel):
    nome: str
    cpf_cnpj: str | None = None
    email: EmailStr | None = None
    telefone: str | None = None
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None


class ClienteUpdate(BaseModel):
    nome: str
    cpf_cnpj: str | None = None
    email: EmailStr | None = None
    telefone: str | None = None
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    ativo: bool


class ClienteResponse(BaseModel):
    id: int
    nome: str
    cpf_cnpj: str | None
    email: EmailStr | None
    telefone: str | None
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    ativo: bool

    class Config:
        orm_mode = True
