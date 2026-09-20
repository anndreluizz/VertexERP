from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin, get_current_user
from app.database.session import SessionLocal
from app.schemas.plano_conta import (
    PlanoContaCreate,
    PlanoContaUpdate,
    PlanoContaResponse,
)
from app.services.plano_conta_service import PlanoContaService

router = APIRouter(
    prefix="/planos-conta",
    tags=["Plano de Contas"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=list[PlanoContaResponse])
def listar(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return PlanoContaService.listar(db)


@router.post("/", response_model=PlanoContaResponse)
def criar(
    dados: PlanoContaCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return PlanoContaService.criar(db, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{conta_id}", response_model=PlanoContaResponse)
def atualizar(
    conta_id: int,
    dados: PlanoContaUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return PlanoContaService.atualizar(db, conta_id, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{conta_id}")
def excluir(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_admin),
):
    try:
        PlanoContaService.excluir(db, conta_id)
        return {
            "success": True,
            "message": "Conta excluída com sucesso.",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
