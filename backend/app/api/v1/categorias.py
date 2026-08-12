from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.categoria import (
    CategoriaCreate,
    CategoriaUpdate,
    CategoriaResponse
)
from app.services.categoria_service import CategoriaService
from app.auth.dependencies import get_current_user, require_admin

router = APIRouter(
    prefix="/categorias",
    tags=["Categorias"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=CategoriaResponse)
def criar_categoria(
    dados: CategoriaCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    return CategoriaService.criar(db, dados)


@router.get("/", response_model=list[CategoriaResponse])
def listar_categorias(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    return CategoriaService.listar(db, skip, limit)


@router.get("/{categoria_id}", response_model=CategoriaResponse)
def buscar_categoria(
    categoria_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    categoria = CategoriaService.buscar_por_id(
        db,
        categoria_id
    )

    if not categoria:
        raise Exception("Categoria não encontrada.")

    return categoria


@router.put("/{categoria_id}", response_model=CategoriaResponse)
def atualizar_categoria(
    categoria_id: int,
    dados: CategoriaUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    return CategoriaService.atualizar(
        db,
        categoria_id,
        dados
    )


@router.delete("/{categoria_id}")
def excluir_categoria(
    categoria_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_admin)
):
    return CategoriaService.excluir(
        db,
        categoria_id
    )