from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class BackupItem(BaseModel):
    nome: str
    tamanho_bytes: int
    criado_em: datetime


class BackupListResponse(BaseModel):
    itens: list[BackupItem]
    pasta: str
    copia_externa: Optional[str] = None
    alerta: Optional[str] = None
