from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.schemas.relatorio import (
    ComparativoEstoqueLojaItem,
    ComparativoLojaItem,
    CurvaAbcItem,
    EstoqueCategoriaItem,
    FunilVendasResponse,
    MargemCategoriaItem,
    RelatorioVendasResponse,
    SugestaoReposicaoItem,
    VendaDiaSemanaItem,
)
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


@router.get("/comparativo-lojas", response_model=list[ComparativoLojaItem])
def comparativo_lojas(
    data_inicio: date | None = None,
    data_fim: date = Query(...),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return RelatorioService.comparativo_lojas(db, data_inicio, data_fim)


@router.get("/funil-vendas", response_model=FunilVendasResponse)
def funil_vendas(
    data_inicio: date | None = None,
    data_fim: date = Query(...),
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return RelatorioService.funil_vendas(db, data_inicio, data_fim, loja_id)


@router.get("/margem-categoria", response_model=list[MargemCategoriaItem])
def margem_categoria(
    data_inicio: date | None = None,
    data_fim: date = Query(...),
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return RelatorioService.margem_por_categoria(db, data_inicio, data_fim, loja_id)


@router.get("/estoque-categoria", response_model=list[EstoqueCategoriaItem])
def estoque_categoria(
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return RelatorioService.estoque_por_categoria(db, loja_id)


@router.get("/vendas-dia-semana", response_model=list[VendaDiaSemanaItem])
def vendas_dia_semana(
    data_inicio: date | None = None,
    data_fim: date = Query(...),
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return RelatorioService.vendas_por_dia_semana(db, data_inicio, data_fim, loja_id)


@router.get("/curva-abc", response_model=list[CurvaAbcItem])
def curva_abc(
    data_inicio: date | None = None,
    data_fim: date = Query(...),
    loja_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return RelatorioService.curva_abc(
        db, data_inicio, data_fim, loja_id, skip, limit
    )


@router.get(
    "/comparativo-estoque", response_model=list[ComparativoEstoqueLojaItem]
)
def comparativo_estoque(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return RelatorioService.comparativo_estoque_lojas(db)


@router.get("/sugestao-reposicao", response_model=list[SugestaoReposicaoItem])
def sugestao_reposicao(
    loja_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return RelatorioService.sugestao_reposicao(db, loja_id, skip, limit)
