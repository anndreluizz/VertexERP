from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.contas_pagar import get_db
from app.auth.dependencies import get_current_user, loja_para_leitura, resolver_loja_id
from app.schemas.conta_pagar import (
    ContaRecorrenteCreate,
    ContaRecorrenteResponse,
    ContaRecorrenteUpdate,
)
from app.services.conta_recorrente_service import ContaRecorrenteService

# Contas fixas mensais (luz, funcionaria, aluguel) -- ver
# ContaRecorrenteService. get_db e' o mesmo objeto de contas_pagar, entao
# o override dos testes vale aqui tambem.
router = APIRouter(
    prefix="/contas-recorrentes",
    tags=["Contas fixas"],
)


@router.get("/", response_model=list[ContaRecorrenteResponse])
def listar(
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return ContaRecorrenteService.listar(db, loja_para_leitura(usuario, loja_id))


@router.post("/", response_model=ContaRecorrenteResponse)
def criar(
    dados: ContaRecorrenteCreate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return ContaRecorrenteService.criar(
            db, dados, resolver_loja_id(db, usuario, loja_id)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{recorrente_id}", response_model=ContaRecorrenteResponse)
def atualizar(
    recorrente_id: int,
    dados: ContaRecorrenteUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    recorrente = ContaRecorrenteService.atualizar(db, recorrente_id, dados)

    if recorrente is None:
        raise HTTPException(status_code=404, detail="Conta fixa não encontrada.")

    return recorrente


@router.delete("/{recorrente_id}")
def parar(
    recorrente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    if not ContaRecorrenteService.parar(db, recorrente_id):
        raise HTTPException(status_code=404, detail="Conta fixa não encontrada.")

    return {"success": True, "message": "Essa conta não vai mais se repetir."}
