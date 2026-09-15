from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, resolver_loja_id
from app.database.session import SessionLocal
from app.schemas.movimento_caixa import (
    MovimentoCaixaCreate,
    MovimentoCaixaResponse,
)
from app.services.movimento_caixa_service import (
    MovimentoCaixaService,
)

router = APIRouter(
    prefix="/movimentos-caixa",
    tags=["Movimentos Caixa"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=MovimentoCaixaResponse)
def criar_movimento(
    dados: MovimentoCaixaCreate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        movimento = MovimentoCaixaService.criar(
            db,
            dados,
            usuario.id,
            resolver_loja_id(db, usuario, loja_id),
        )

        return MovimentoCaixaResponse.from_orm(movimento)

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.get("/", response_model=list[MovimentoCaixaResponse])
def listar_movimentos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    movimentos = MovimentoCaixaService.listar(db, skip, limit)

    return [
        MovimentoCaixaResponse.from_orm(m)
        for m in movimentos
    ]


@router.get(
    "/caixa/{caixa_id}",
    response_model=list[MovimentoCaixaResponse],
)
def listar_por_caixa(
    caixa_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    movimentos = MovimentoCaixaService.listar_por_caixa(
        db,
        caixa_id,
    )

    return [
        MovimentoCaixaResponse.from_orm(m)
        for m in movimentos
    ]


@router.get(
    "/tipo/{tipo}",
    response_model=list[MovimentoCaixaResponse],
)
def listar_por_tipo(
    tipo: str,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    movimentos = MovimentoCaixaService.listar_por_tipo(db, tipo)

    return [
        MovimentoCaixaResponse.from_orm(m)
        for m in movimentos
    ]