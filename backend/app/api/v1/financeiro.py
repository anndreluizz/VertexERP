from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.schemas.movimento_fiado import (
    MovimentoFiadoCreate,
    MovimentoFiadoResponse,
    SaldoFiadoResponse,
)
from app.services.movimento_fiado_service import MovimentoFiadoService

router = APIRouter(
    prefix="/fiado",
    tags=["Fiado"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/movimentos", response_model=MovimentoFiadoResponse)
def criar_movimento(
    dados: MovimentoFiadoCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        movimento = MovimentoFiadoService.criar(
            db,
            dados,
            usuario.id,
        )

        return MovimentoFiadoResponse.from_orm(movimento)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/movimentos", response_model=list[MovimentoFiadoResponse])
def listar_movimentos(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    movimentos = MovimentoFiadoService.listar(db)

    return [
        MovimentoFiadoResponse.from_orm(m)
        for m in movimentos
    ]


@router.get(
    "/movimentos/cliente/{cliente_id}",
    response_model=list[MovimentoFiadoResponse],
)
def listar_por_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    movimentos = MovimentoFiadoService.listar_por_cliente(
        db,
        cliente_id,
    )

    return [
        MovimentoFiadoResponse.from_orm(m)
        for m in movimentos
    ]


@router.get(
    "/saldo/{cliente_id}",
    response_model=SaldoFiadoResponse,
)
def saldo_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    saldo = MovimentoFiadoService.saldo_por_cliente(db, cliente_id)

    return SaldoFiadoResponse(cliente_id=cliente_id, saldo=saldo)
