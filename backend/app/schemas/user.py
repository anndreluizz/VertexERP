from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str


class UserLogin(BaseModel):
    email: EmailStr
    senha: str


class UserAdminUpdate(BaseModel):
    admin: bool


class UserAtivoUpdate(BaseModel):
    ativo: bool


class UserResponse(BaseModel):
    id: int
    nome: str
    email: EmailStr
    ativo: bool
    admin: bool

    class Config:
        orm_mode = True