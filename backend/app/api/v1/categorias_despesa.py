from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import exigir_permissao, get_current_user
from app.database.session import SessionLocal
from app.schemas.categoria_despesa import (
    CategoriaDespesaCreate,
    CategoriaDespesaUpdate,
    CategoriaDespesaResponse,
)
from app.services.categoria_despesa_service import (
    CategoriaDespesaService,
)

router = APIRouter(
    prefix="/categorias-despesa",
    tags=["Categorias de Despesa"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=list[CategoriaDespesaResponse])
def listar(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return CategoriaDespesaService.listar(db)


@router.post("/", response_model=CategoriaDespesaResponse)
def criar(
    dados: CategoriaDespesaCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return CategoriaDespesaService.criar(db, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{categoria_id}", response_model=CategoriaDespesaResponse)
def atualizar(
    categoria_id: int,
    dados: CategoriaDespesaUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return CategoriaDespesaService.atualizar(
            db, categoria_id, dados
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{categoria_id}")
def excluir(
    categoria_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(exigir_permissao("categorias_despesa.excluir")),
):
    try:
        CategoriaDespesaService.excluir(db, categoria_id)
        return {
            "success": True,
            "message": "Categoria excluída com sucesso.",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
