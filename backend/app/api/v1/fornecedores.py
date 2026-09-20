from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.fornecedor import (
    FornecedorCreate,
    FornecedorUpdate,
    FornecedorResponse,
)
from app.schemas.nfe_importacao import NFeImportarRequest, NFePreviewResponse
from app.services.fornecedor_service import FornecedorService
from app.services.importacao_nfe_service import ImportacaoNfeService
from app.auth.dependencies import (
    exigir_permissao,
    get_current_user,
    resolver_loja_id,
)

router = APIRouter(
    prefix="/fornecedores",
    tags=["Fornecedores"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=FornecedorResponse)
def criar(
    dados: FornecedorCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FornecedorService.criar(db, dados)


@router.get("/", response_model=list[FornecedorResponse])
def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FornecedorService.listar(db, skip, limit)


@router.get("/{fornecedor_id}", response_model=FornecedorResponse)
def buscar(
    fornecedor_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FornecedorService.buscar(db, fornecedor_id)


@router.put("/{fornecedor_id}", response_model=FornecedorResponse)
def atualizar(
    fornecedor_id: int,
    dados: FornecedorUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FornecedorService.atualizar(
        db,
        fornecedor_id,
        dados,
    )


@router.delete("/{fornecedor_id}")
def excluir(
    fornecedor_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(exigir_permissao("fornecedores.excluir")),
):
    return FornecedorService.excluir(
        db,
        fornecedor_id,
    )


@router.post("/importar-nfe", response_model=NFePreviewResponse)
def importar_nfe_preview(
    dados: NFeImportarRequest,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """So' leitura -- extrai e casa com o que ja existe, nao grava nada.
    Confirmar de verdade e' POST /compras/importar-nfe."""

    return ImportacaoNfeService.pre_visualizar(
        db, dados, resolver_loja_id(db, usuario, loja_id)
    )
