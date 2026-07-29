from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.schemas.venda import (
    VendaCreate,
    VendaResponse,
)
from app.services.venda_service import VendaService

router = APIRouter(
    prefix="/vendas",
    tags=["Vendas"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=list[VendaResponse])
def listar(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return VendaService.listar(db)


@router.get("/{venda_id}", response_model=VendaResponse)
def buscar(
    venda_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    venda = VendaService.buscar(db, venda_id)

    if not venda:
        raise HTTPException(
            status_code=404,
            detail="Venda não encontrada"
        )

    return venda


@router.post("/", response_model=VendaResponse, status_code=201)
def criar(
    dados: VendaCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return VendaService.criar(db, dados, usuario.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{venda_id}")
def excluir(
    venda_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    ok = VendaService.excluir(db, venda_id, usuario.id)

    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Venda não encontrada"
        )

    return {
        "success": True,
        "message": "Venda cancelada com sucesso."
    }