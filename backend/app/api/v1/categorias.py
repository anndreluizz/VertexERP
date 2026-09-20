from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.categoria import (
    CategoriaCreate,
    CategoriaUpdate,
    CategoriaResponse
)
from app.services.categoria_service import CategoriaService
from app.auth.dependencies import exigir_permissao, get_current_user

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
    try:
        return CategoriaService.criar(db, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[CategoriaResponse])
def listar_categorias(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    return CategoriaService.listar(db)


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
    usuario=Depends(exigir_permissao("categorias.excluir"))
):
    return CategoriaService.excluir(
        db,
        categoria_id
    )