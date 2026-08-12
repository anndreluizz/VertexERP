from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.schemas.movimento_fiado import (
    CompraFiadoCreate,
    FichaClienteResponse,
    MovimentoFiadoResponse,
    PagamentoFiadoCreate,
)
from app.services.fiado_service import FiadoService

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


@router.get("/saldos", response_model=dict[int, float])
def saldos_por_cliente(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FiadoService.saldos_por_cliente(db)


@router.get("/cliente/{cliente_id}", response_model=FichaClienteResponse)
def ficha_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FiadoService.ficha_cliente(db, cliente_id)


@router.post(
    "/pagamento",
    response_model=MovimentoFiadoResponse,
    status_code=201,
)
def registrar_pagamento(
    dados: PagamentoFiadoCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FiadoService.registrar_pagamento(
        db,
        dados.cliente_id,
        float(dados.valor),
        dados.descricao,
        usuario.id,
        dados.data,
    )


@router.post(
    "/compra",
    response_model=MovimentoFiadoResponse,
    status_code=201,
)
def registrar_compra_manual(
    dados: CompraFiadoCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FiadoService.registrar_compra_manual(
        db,
        dados.cliente_id,
        float(dados.valor),
        dados.descricao,
        dados.data,
        usuario.id,
    )
