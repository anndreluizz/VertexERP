from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel
from typing import Optional


class ContaReceberBase(BaseModel):
    cliente_id: int
    venda_id: Optional[int] = None
    data_vencimento: datetime
    valor: Decimal
    observacao: Optional[str] = None


class ContaReceberCreate(ContaReceberBase):
    pass


class ContaReceberUpdate(BaseModel):
    data_vencimento: Optional[datetime] = None
    valor: Optional[Decimal] = None
    observacao: Optional[str] = None
    status: Optional[str] = None


class ContaReceberResponse(ContaReceberBase):
    id: int
    data_emissao: datetime
    data_recebimento: Optional[datetime] = None
    status: str

    class Config:
        orm_mode = True