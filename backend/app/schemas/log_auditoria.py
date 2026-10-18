from datetime import datetime

from app.schemas.base import Schema


class LogAuditoriaResponse(Schema):
    id: int
    usuario_id: int | None = None
    usuario_nome: str | None = None
    acao: str
    detalhes: str | None = None
    ip: str | None = None
    data: datetime
