from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.schemas.movimento_estoque import (
    MovimentoEstoqueCreate,
    MovimentoEstoqueResponse,
)
from app.services.movimento_estoque_service import MovimentoEstoqueService

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


@router.post("/movimentos", response_model=MovimentoEstoqueResponse)
def criar_movimento(
    dados: MovimentoEstoqueCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        movimento = MovimentoEstoqueService.criar(
            db,
            dados,
            usuario.id,
        )

        return MovimentoEstoqueResponse.from_orm(movimento)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/movimentos", response_model=list[MovimentoEstoqueResponse])
def listar_movimentos(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    movimentos = MovimentoEstoqueService.listar(db)

    return [
        MovimentoEstoqueResponse.from_orm(m)
        for m in movimentos
    ]


@router.get(
    "/movimentos/produto/{produto_id}",
    response_model=list[MovimentoEstoqueResponse],
)
def listar_por_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    movimentos = MovimentoEstoqueService.listar_por_produto(
        db,
        produto_id,
    )

    return [
        MovimentoEstoqueResponse.from_orm(m)
        for m in movimentos
    ]
