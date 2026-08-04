from pydantic import BaseModel


class DeviceTokenCreate(BaseModel):
    token: str
    plataforma: str = "ANDROID"


class DeviceTokenResponse(BaseModel):
    id: int
    usuario_id: int
    token: str
    plataforma: str

    class Config:
        orm_mode = True
