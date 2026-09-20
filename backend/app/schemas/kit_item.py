from pydantic import BaseModel


class KitItemCreate(BaseModel):
    produto_componente_id: int
    quantidade: int = 1


class KitItemResponse(BaseModel):
    id: int
    kit_id: int
    produto_componente_id: int
    produto_componente_nome: str | None = None
    quantidade: int

    class Config:
        orm_mode = True
