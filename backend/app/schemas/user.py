from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str


class UserLogin(BaseModel):
    email: EmailStr
    senha: str


class UserUpdate(BaseModel):
    nome: str | None = None
    ativo: bool | None = None
    admin: bool | None = None


class UserResponse(BaseModel):
    id: int
    nome: str
    email: EmailStr
    ativo: bool
    admin: bool

    class Config:
        orm_mode = True