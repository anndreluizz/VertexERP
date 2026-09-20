from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin, get_current_user
from app.database.session import SessionLocal
from app.schemas.centro_custo import (
    CentroCustoCreate,
    CentroCustoUpdate,
    CentroCustoResponse,
)
from app.services.centro_custo_service import (
    CentroCustoService,
)

router = APIRouter(
    prefix="/centros-custo",
    tags=["Centros de Custo"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=list[CentroCustoResponse])
def listar(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return CentroCustoService.listar(db)


@router.post("/", response_model=CentroCustoResponse)
def criar(
    dados: CentroCustoCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return CentroCustoService.criar(db, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{centro_id}", response_model=CentroCustoResponse)
def atualizar(
    centro_id: int,
    dados: CentroCustoUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return CentroCustoService.atualizar(
            db, centro_id, dados
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{centro_id}")
def excluir(
    centro_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_admin),
):
    try:
        CentroCustoService.excluir(db, centro_id)
        return {
            "success": True,
            "message": "Centro de custo excluído com sucesso.",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
