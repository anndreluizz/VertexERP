from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin, get_current_user, resolver_loja_id
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
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return ProdutoService.listar(db, skip, limit, loja_id)


@router.get("/{produto_id}", response_model=ProdutoResponse)
def buscar(
    produto_id: int,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    produto = ProdutoService.buscar(db, produto_id, loja_id)

    if not produto:
        raise HTTPException(
            status_code=404,
            detail="Produto não encontrado"
        )

    return produto


@router.post("/", response_model=ProdutoResponse, status_code=201)
def criar(
    dados: ProdutoCreate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return ProdutoService.criar(
            db, dados, resolver_loja_id(db, usuario, loja_id)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{produto_id}/foto")
def obter_foto(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    produto = ProdutoService.buscar(db, produto_id)

    if not produto or not produto.foto:
        raise HTTPException(
            status_code=404,
            detail="Produto sem foto cadastrada."
        )

    return Response(content=produto.foto, media_type="image/jpeg")


@router.put("/{produto_id}", response_model=ProdutoResponse)
def atualizar(
    produto_id: int,
    dados: ProdutoUpdate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    produto = ProdutoService.atualizar(
        db,
        produto_id,
        dados,
        resolver_loja_id(db, usuario, loja_id),
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
    usuario=Depends(get_current_admin),
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