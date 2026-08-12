from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.database.session import SessionLocal

from app.schemas.conta_pagar import (
    ContaPagarCreate,
    ContaPagarUpdate,
    ContaPagarResponse,
)

from app.services.conta_pagar_service import (
    ContaPagarService,
)

router = APIRouter(
    prefix="/contas-pagar",
    tags=["Contas a Pagar"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=ContaPagarResponse)
def criar(
    dados: ContaPagarCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:

        conta = ContaPagarService.criar(
            db,
            dados,
        )

        return ContaPagarResponse.from_orm(conta)

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.get("/", response_model=list[ContaPagarResponse])
def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    contas = ContaPagarService.listar(db, skip, limit)

    return [
        ContaPagarResponse.from_orm(c)
        for c in contas
    ]


@router.get(
    "/pendentes",
    response_model=list[ContaPagarResponse],
)
def listar_pendentes(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    # Sem paginação de propósito: essa lista também alimenta o cálculo
    # do fluxo de caixa (financeiro_service), que precisa do total real.

    contas = ContaPagarService.listar_pendentes(db)

    return [
        ContaPagarResponse.from_orm(c)
        for c in contas
    ]


@router.get(
    "/pagas",
    response_model=list[ContaPagarResponse],
)
def listar_pagas(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    contas = ContaPagarService.listar_pagas(db, skip, limit)

    return [
        ContaPagarResponse.from_orm(c)
        for c in contas
    ]


@router.put(
    "/{conta_id}",
    response_model=ContaPagarResponse,
)
def atualizar(
    conta_id: int,
    dados: ContaPagarUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    try:

        conta = ContaPagarService.atualizar(
            db,
            conta_id,
            dados,
        )

        return ContaPagarResponse.from_orm(conta)

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.post(
    "/{conta_id}/pagar",
    response_model=ContaPagarResponse,
)
def pagar(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    try:

        conta = ContaPagarService.pagar(
            db,
            conta_id,
            usuario.id,
        )

        return ContaPagarResponse.from_orm(conta)

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.post(
    "/{conta_id}/cancelar",
    response_model=ContaPagarResponse,
)
def cancelar(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_admin),
):

    try:

        conta = ContaPagarService.cancelar(
            db,
            conta_id,
        )

        return ContaPagarResponse.from_orm(conta)

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )