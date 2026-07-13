from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.schemas.produto import (
    ProdutoCreate,
    ProdutoUpdate,
    ProdutoResponse,
)
from app.services.produto_service import ProdutoService

router = APIRouter(
    prefix="/produtos",
    tags=["Produtos"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=list[ProdutoResponse])
def listar(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return ProdutoService.listar(db)


@router.get("/{produto_id}", response_model=ProdutoResponse)
def buscar(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    produto = ProdutoService.buscar(db, produto_id)

    if not produto:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado"
        )

    return produto


# ===== TESTE TEMPORÁRIO =====
# Removemos o response_model apenas para descobrir
# onde está o erro de serialização.
@router.post("/", status_code=201)
def criar(
    dados: ProdutoCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    produto = ProdutoService.criar(db, dados)
    return produto


@router.put("/{produto_id}", response_model=ProdutoResponse)
def atualizar(
    produto_id: int,
    dados: ProdutoUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    produto = ProdutoService.atualizar(
        db,
        produto_id,
        dados
    )

    if not produto:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado"
        )

    return produto


@router.delete("/{produto_id}")
def excluir(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    ok = ProdutoService.excluir(db, produto_id)

    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado"
        )

    return {
        "success": True,
        "message": "Produto excluído com sucesso."
    }