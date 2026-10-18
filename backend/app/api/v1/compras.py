from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    exigir_permissao,
    get_current_user,
    resolver_loja_id,
)
from app.database.session import SessionLocal

from app.schemas.compra import (
    CompraCreate,
    CompraResponse,
)
from app.schemas.nfe_importacao import ImportarNFeConfirmarRequest

from app.services.compra_service import CompraService
from app.services.importacao_nfe_service import ImportacaoNfeService

router = APIRouter(
    prefix="/compras",
    tags=["Compras"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=CompraResponse)
def criar(
    dados: CompraCreate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:

        compra = CompraService.criar(
            db,
            dados,
            usuario.id,
            resolver_loja_id(db, usuario, loja_id),
        )

        return CompraResponse.model_validate(compra)

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.post("/importar-nfe", response_model=CompraResponse)
def importar_nfe_confirmar(
    dados: ImportarNFeConfirmarRequest,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:

        compra = ImportacaoNfeService.confirmar(
            db,
            dados,
            usuario.id,
            resolver_loja_id(db, usuario, loja_id),
        )

        return CompraResponse.model_validate(compra)

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.get("/", response_model=list[CompraResponse])
def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    compras = CompraService.listar(db, skip, limit)

    return [
        CompraResponse.model_validate(c)
        for c in compras
    ]


@router.get("/{compra_id}", response_model=CompraResponse)
def buscar(
    compra_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    compra = CompraService.buscar(
        db,
        compra_id,
    )

    if not compra:

        raise HTTPException(
            status_code=404,
            detail="Compra não encontrada.",
        )

    return CompraResponse.model_validate(compra)


@router.delete("/{compra_id}")
def cancelar(
    compra_id: int,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(exigir_permissao("compras.cancelar")),
):
    try:

        if not CompraService.cancelar(
            db,
            compra_id,
            usuario.id,
            resolver_loja_id(db, usuario, loja_id),
        ):

            raise HTTPException(
                status_code=404,
                detail="Compra não encontrada.",
            )

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    return {
        "message": "Compra cancelada com sucesso."
    }
