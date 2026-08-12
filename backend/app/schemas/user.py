from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str


class UserLogin(BaseModel):
    email: EmailStr
    senha: str
    # opcional -- so o app mobile envia (ex.: "Android - Pixel 7"), pra
    # aparecer identificavel na tela de Sessoes. Desktop nao manda nada
    # e continua funcionando igual (fica None).
    dispositivo: str | None = None


class UserUpdate(BaseModel):
    nome: str | None = None
    ativo: bool | None = None
    admin: bool | None = None


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
    dois_fatores_ativo: bool = False

    class Config:
        orm_mode = True