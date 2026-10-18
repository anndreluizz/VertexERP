from datetime import datetime
from typing import Optional

from app.schemas.base import Schema


class BackupItem(Schema):
    nome: str
    tamanho_bytes: int
    criado_em: datetime


class BackupListResponse(Schema):
    itens: list[BackupItem]
    pasta: str
    copia_externa: Optional[str] = None
    alerta: Optional[str] = None
