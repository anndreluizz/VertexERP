from datetime import datetime

from pydantic import BaseModel


class LogAuditoriaResponse(BaseModel):
    id: int
    usuario_id: int | None = None
    usuario_nome: str | None = None
    acao: str
    detalhes: str | None = None
    ip: str | None = None
    data: datetime

    class Config:
        orm_mode = True
