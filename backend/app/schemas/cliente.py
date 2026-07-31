from datetime import date, datetime

from pydantic import BaseModel, EmailStr


class ClienteCreate(BaseModel):
    nome: str
    cpf_cnpj: str | None = None
    email: EmailStr | None = None
    telefone: str | None = None
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    data_nascimento: date | None = None
    limite_credito: float | None = None

    # imagem em base64 (entrada apenas); None mantem a foto atual
    foto_base64: str | None = None


class ClienteUpdate(BaseModel):
    nome: str
    cpf_cnpj: str | None = None
    email: EmailStr | None = None
    telefone: str | None = None
    endereco: str | None = None
    cidade: str | None = None
    estado: str | None = None
    ativo: bool
    data_nascimento: date | None = None
    limite_credito: float | None = None

    foto_base64: str | None = None


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
    criado_em: datetime
    data_nascimento: date | None = None
    limite_credito: float | None = None
    tem_foto: bool = False

    class Config:
        orm_mode = True


class ClienteObservacaoCreate(BaseModel):
    texto: str


class ClienteObservacaoResponse(BaseModel):
    id: int
    cliente_id: int
    usuario_id: int
    texto: str
    criado_em: datetime

    class Config:
        orm_mode = True
