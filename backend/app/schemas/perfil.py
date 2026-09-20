from pydantic import BaseModel


class PerfilCreate(BaseModel):
    nome: str
    permissoes: list[str] = []


class PerfilUpdate(BaseModel):
    nome: str
    permissoes: list[str] = []


class PerfilResponse(BaseModel):
    id: int
    nome: str
    permissoes: list[str]

    class Config:
        orm_mode = True
