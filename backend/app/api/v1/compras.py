from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.database.session import SessionLocal

from app.schemas.compra import (
    CompraCreate,
    CompraResponse,
)

from app.services.compra_service import CompraService

router = APIRouter(
    prefix="/compras",
    tags=["Compras"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=CompraResponse)
def criar(
    dados: CompraCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:

        compra = CompraService.criar(
            db,
            dados,
        )

        return CompraResponse.from_orm(compra)

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.get("/", response_model=list[CompraResponse])
def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    compras = CompraService.listar(db, skip, limit)

    return [
        CompraResponse.from_orm(c)
        for c in compras
    ]


@router.get("/{compra_id}", response_model=CompraResponse)
def buscar(
    compra_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    compra = CompraService.buscar(
        db,
        compra_id,
    )

    if not compra:

        raise HTTPException(
            status_code=404,
            detail="Compra não encontrada.",
        )

    return CompraResponse.from_orm(compra)


@router.delete("/{compra_id}")
def excluir(
    compra_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_admin),
):

    if not CompraService.excluir(
        db,
        compra_id,
    ):

        raise HTTPException(
            status_code=404,
            detail="Compra não encontrada.",
        )

    return {
        "message": "Compra excluída com sucesso."
    }