from datetime import datetime

from pydantic import BaseModel


class RefreshRequest(BaseModel):
    refresh_token: str


class SessaoResponse(BaseModel):
    id: int
    dispositivo: str | None
    criado_em: datetime
    ultimo_uso_em: datetime

    class Config:
        orm_mode = True
