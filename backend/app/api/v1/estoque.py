from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.schemas.movimento_estoque import (
    MovimentoEstoqueCreate,
    MovimentoEstoqueResponse,
)
from app.services.estoque_service import EstoqueService

router = APIRouter(
    prefix="/estoque",
    tags=["Estoque"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post(
    "/ajuste",
    response_model=MovimentoEstoqueResponse,
    status_code=201,
)
def ajustar_estoque(
    dados: MovimentoEstoqueCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return EstoqueService.ajustar(db, dados, usuario.id)


@router.get("/movimentos", response_model=list[MovimentoEstoqueResponse])
def listar_movimentos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return EstoqueService.listar(db, skip, limit)


@router.get(
    "/movimentos/{produto_id}",
    response_model=list[MovimentoEstoqueResponse],
)
def listar_movimentos_por_produto(
    produto_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return EstoqueService.listar_por_produto(db, produto_id, skip, limit)
