from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str


class UserLogin(BaseModel):
    email: EmailStr
    senha: str


class UserResponse(BaseModel):
    id: int
    nome: str
    email: EmailStr
    ativo: bool
    admin: bool

    class Config:
        orm_mode = True