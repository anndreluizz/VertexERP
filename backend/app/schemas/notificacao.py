from datetime import datetime

from app.schemas.base import Schema


class NotificacaoResponse(Schema):
    id: int
    titulo: str
    corpo: str
    lida: bool
    criado_em: datetime


class ContagemNaoLidasResponse(Schema):
    nao_lidas: int
