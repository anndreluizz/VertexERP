from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.fornecedor import (
    FornecedorCreate,
    FornecedorUpdate,
    FornecedorResponse,
)
from app.services.fornecedor_service import FornecedorService
from app.auth.dependencies import get_current_user

router = APIRouter(
    prefix="/fornecedores",
    tags=["Fornecedores"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=FornecedorResponse)
def criar(
    dados: FornecedorCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FornecedorService.criar(db, dados)


@router.get("/", response_model=list[FornecedorResponse])
def listar(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FornecedorService.listar(db)


@router.get("/{fornecedor_id}", response_model=FornecedorResponse)
def buscar(
    fornecedor_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FornecedorService.buscar(db, fornecedor_id)


@router.put("/{fornecedor_id}", response_model=FornecedorResponse)
def atualizar(
    fornecedor_id: int,
    dados: FornecedorUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FornecedorService.atualizar(
        db,
        fornecedor_id,
        dados,
    )


@router.delete("/{fornecedor_id}")
def excluir(
    fornecedor_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FornecedorService.excluir(
        db,
        fornecedor_id,
    )