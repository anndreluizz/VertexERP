from datetime import datetime

from app.schemas.base import Schema


class RefreshRequest(Schema):
    refresh_token: str


class SessaoResponse(Schema):
    id: int
    dispositivo: str | None = None
    criado_em: datetime
    ultimo_uso_em: datetime
