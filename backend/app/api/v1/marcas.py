from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.marca import (
    MarcaCreate,
    MarcaUpdate,
    MarcaResponse
)
from app.services.marca_service import MarcaService
from app.auth.dependencies import exigir_permissao, get_current_user

router = APIRouter(
    prefix="/marcas",
    tags=["Marcas"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=MarcaResponse)
def criar_marca(
    dados: MarcaCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    try:
        return MarcaService.criar(db, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[MarcaResponse])
def listar_marcas(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    return MarcaService.listar(db)


@router.get("/{marca_id}", response_model=MarcaResponse)
def buscar_marca(
    marca_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    marca = MarcaService.buscar_por_id(
        db,
        marca_id
    )

    if not marca:
        raise HTTPException(status_code=404, detail="Marca não encontrada.")

    return marca


@router.put("/{marca_id}", response_model=MarcaResponse)
def atualizar_marca(
    marca_id: int,
    dados: MarcaUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    try:
        return MarcaService.atualizar(
            db,
            marca_id,
            dados
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{marca_id}")
def excluir_marca(
    marca_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(exigir_permissao("marcas.excluir"))
):
    try:
        return MarcaService.excluir(
            db,
            marca_id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
