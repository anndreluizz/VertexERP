from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.loja import LojaCreate, LojaResponse, LojaUpdate
from app.services.loja_service import LojaService
from app.auth.dependencies import get_current_admin, get_current_user

router = APIRouter(
    prefix="/lojas",
    tags=["Lojas"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=list[LojaResponse])
def listar_lojas(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return LojaService.listar(db)


@router.post("/", response_model=LojaResponse)
def criar_loja(
    dados: LojaCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_admin),
):
    try:
        return LojaService.criar(db, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{loja_id}", response_model=LojaResponse)
def atualizar_loja(
    loja_id: int,
    dados: LojaUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_admin),
):
    try:
        return LojaService.atualizar(db, loja_id, dados)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
