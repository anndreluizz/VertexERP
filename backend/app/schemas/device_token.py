
from app.schemas.base import Schema


class DeviceTokenCreate(Schema):
    token: str
    plataforma: str = "ANDROID"


class DeviceTokenResponse(Schema):
    id: int
    usuario_id: int
    token: str
    plataforma: str
