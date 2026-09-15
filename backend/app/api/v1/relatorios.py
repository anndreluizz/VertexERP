from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.schemas.relatorio import RelatorioVendasResponse
from app.services.relatorio_service import RelatorioService

router = APIRouter(
    prefix="/relatorios",
    tags=["Relatórios"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/vendas", response_model=RelatorioVendasResponse)
def relatorio_vendas(
    data_inicio: date | None = None,
    data_fim: date = Query(...),
    cliente_id: int | None = None,
    produto_id: int | None = None,
    categoria: str | None = None,
    forma_pagamento: str | None = None,
    status: str | None = None,
    loja_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    top_produtos_limite: int = Query(5, ge=1, le=20),
    top_produtos_ordenar_por: str = Query("quantidade"),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return RelatorioService.vendas_geral(
        db,
        data_inicio,
        data_fim,
        cliente_id=cliente_id,
        produto_id=produto_id,
        categoria=categoria,
        forma_pagamento=forma_pagamento,
        status=status,
        loja_id=loja_id,
        skip=skip,
        limit=limit,
        top_produtos_limite=top_produtos_limite,
        top_produtos_ordenar_por=top_produtos_ordenar_por,
    )
