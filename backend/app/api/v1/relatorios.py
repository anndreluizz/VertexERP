from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import exigir_financeiro, get_current_user, loja_para_leitura
from app.database.session import SessionLocal
from app.schemas.relatorio import (
    CategoriaSemVendaItem,
    ComparativoEstoqueLojaItem,
    ComparativoLojaItem,
    CurvaAbcItem,
    EstoqueCategoriaItem,
    FunilVendasResponse,
    GastoCompraMensalItem,
    MargemCategoriaItem,
    PrazoFornecedorItem,
    RankingFornecedorItem,
    RelatorioVendasResponse,
    SugestaoReposicaoItem,
    VendaDiaSemanaItem,
    VendaDiaSemanaHoraItem,
)
from app.services.relatorio_service import RelatorioService

router = APIRouter(
    prefix="/relatorios",
    tags=["Relatórios"],
    dependencies=[Depends(exigir_financeiro)],
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
    loja_id = loja_para_leitura(usuario, loja_id)
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
    loja_id = loja_para_leitura(usuario, loja_id)
    return RelatorioService.funil_vendas(db, data_inicio, data_fim, loja_id)


@router.get("/margem-categoria", response_model=list[MargemCategoriaItem])
def margem_categoria(
    data_inicio: date | None = None,
    data_fim: date = Query(...),
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    loja_id = loja_para_leitura(usuario, loja_id)
    return RelatorioService.margem_por_categoria(db, data_inicio, data_fim, loja_id)


@router.get("/estoque-categoria", response_model=list[EstoqueCategoriaItem])
def estoque_categoria(
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    loja_id = loja_para_leitura(usuario, loja_id)
    return RelatorioService.estoque_por_categoria(db, loja_id)


@router.get("/vendas-dia-semana", response_model=list[VendaDiaSemanaItem])
def vendas_dia_semana(
    data_inicio: date | None = None,
    data_fim: date = Query(...),
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    loja_id = loja_para_leitura(usuario, loja_id)
    return RelatorioService.vendas_por_dia_semana(db, data_inicio, data_fim, loja_id)


@router.get("/vendas-dia-semana-hora", response_model=list[VendaDiaSemanaHoraItem])
def vendas_dia_semana_hora(
    data_inicio: date | None = None,
    data_fim: date = Query(...),
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    loja_id = loja_para_leitura(usuario, loja_id)
    return RelatorioService.vendas_dia_semana_hora(db, data_inicio, data_fim, loja_id)


@router.get("/gasto-compras-mensal", response_model=list[GastoCompraMensalItem])
def gasto_compras_mensal(
    data_inicio: date | None = None,
    data_fim: date = Query(...),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return RelatorioService.gasto_compras_mensal(db, data_inicio, data_fim)


@router.get("/ranking-fornecedores", response_model=list[RankingFornecedorItem])
def ranking_fornecedores(
    data_inicio: date | None = None,
    data_fim: date = Query(...),
    limite: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return RelatorioService.ranking_fornecedores(db, data_inicio, data_fim, limite)


@router.get("/prazo-fornecedores", response_model=list[PrazoFornecedorItem])
def prazo_fornecedores(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return RelatorioService.prazo_medio_pagamento_fornecedores(db)


@router.get("/categorias-sem-venda", response_model=list[CategoriaSemVendaItem])
def categorias_sem_venda(
    dias: int = Query(90, ge=1),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return RelatorioService.categorias_sem_venda(db, dias)


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
    loja_id = loja_para_leitura(usuario, loja_id)
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
    loja_id = loja_para_leitura(usuario, loja_id)
    return RelatorioService.sugestao_reposicao(db, loja_id, skip, limit)
