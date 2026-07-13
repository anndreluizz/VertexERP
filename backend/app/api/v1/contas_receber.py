from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal

from app.schemas.conta_receber import (
    ContaReceberCreate,
    ContaReceberUpdate,
    ContaReceberResponse,
)

from app.services.conta_receber_service import ContaReceberService

router = APIRouter(
    prefix="/contas-receber",
    tags=["Contas a Receber"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=ContaReceberResponse)
def criar(
    dados: ContaReceberCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        conta = ContaReceberService.criar(
            db,
            dados,
        )

        return ContaReceberResponse.from_orm(conta)

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.get("/", response_model=list[ContaReceberResponse])
def listar(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    contas = ContaReceberService.listar(db)

    return [
        ContaReceberResponse.from_orm(c)
        for c in contas
    ]


@router.get(
    "/pendentes",
    response_model=list[ContaReceberResponse],
)
def listar_pendentes(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    contas = ContaReceberService.listar_pendentes(db)

    return [
        ContaReceberResponse.from_orm(c)
        for c in contas
    ]


@router.get(
    "/recebidas",
    response_model=list[ContaReceberResponse],
)
def listar_recebidas(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    contas = ContaReceberService.listar_recebidas(db)

    return [
        ContaReceberResponse.from_orm(c)
        for c in contas
    ]


@router.get(
    "/cliente/{cliente_id}",
    response_model=list[ContaReceberResponse],
)
def listar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    contas = ContaReceberService.listar_por_cliente(
        db,
        cliente_id,
    )

    return [
        ContaReceberResponse.from_orm(c)
        for c in contas
    ]


@router.put(
    "/{conta_id}",
    response_model=ContaReceberResponse,
)
def atualizar(
    conta_id: int,
    dados: ContaReceberUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        conta = ContaReceberService.atualizar(
            db,
            conta_id,
            dados,
        )

        return ContaReceberResponse.from_orm(conta)

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.post(
    "/{conta_id}/receber",
    response_model=ContaReceberResponse,
)
def receber(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        conta = ContaReceberService.receber(
            db,
            conta_id,
            usuario["id"],   # <-- usuário do token JWT
        )

        return ContaReceberResponse.from_orm(conta)

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.post(
    "/{conta_id}/cancelar",
    response_model=ContaReceberResponse,
)
def cancelar(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        conta = ContaReceberService.cancelar(
            db,
            conta_id,
        )

        return ContaReceberResponse.from_orm(conta)

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )