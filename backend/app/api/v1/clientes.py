from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.cliente import (
    ClienteCreate,
    ClienteUpdate,
    ClienteResponse
)
from app.services.cliente_service import ClienteService
from app.auth.dependencies import get_current_user

router = APIRouter(
    prefix="/clientes",
    tags=["Clientes"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=ClienteResponse)
def criar_cliente(
    dados: ClienteCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    try:
        return ClienteService.criar(db, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[ClienteResponse])
def listar_clientes(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    return ClienteService.listar(db)


@router.get("/{cliente_id}", response_model=ClienteResponse)
def buscar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    cliente = ClienteService.buscar_por_id(db, cliente_id)

    if not cliente:
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado.",
        )

    return cliente


@router.put("/{cliente_id}", response_model=ClienteResponse)
def atualizar_cliente(
    cliente_id: int,
    dados: ClienteUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    try:
        return ClienteService.atualizar(
            db,
            cliente_id,
            dados
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{cliente_id}")
def excluir_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    try:
        return ClienteService.excluir(
            db,
            cliente_id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
