from datetime import datetime

from pydantic import BaseModel


class BackupItem(BaseModel):
    nome: str
    tamanho_bytes: int
    criado_em: datetime


class BackupListResponse(BaseModel):
    itens: list[BackupItem]
    pasta: str
