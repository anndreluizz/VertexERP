from pydantic import BaseModel


class PlanoContaCreate(BaseModel):
    codigo: str | None = None
    nome: str
    tipo: str
    conta_pai_id: int | None = None


class PlanoContaUpdate(BaseModel):
    codigo: str | None = None
    nome: str
    tipo: str
    conta_pai_id: int | None = None
    ativo: bool = True


class PlanoContaResponse(BaseModel):
    id: int
    codigo: str | None = None
    nome: str
    tipo: str
    conta_pai_id: int | None = None
    conta_pai_nome: str | None = None
    ativo: bool

    class Config:
        orm_mode = True
