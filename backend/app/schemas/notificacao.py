from datetime import datetime

from pydantic import BaseModel


class NotificacaoResponse(BaseModel):
    id: int
    titulo: str
    corpo: str
    lida: bool
    criado_em: datetime

    class Config:
        orm_mode = True


class ContagemNaoLidasResponse(BaseModel):
    nao_lidas: int
