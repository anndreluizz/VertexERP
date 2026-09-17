from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, resolver_loja_id
from app.database.session import SessionLocal

from app.schemas.pdv import ProdutoPDV
from app.services.pdv_service import PDVService


router = APIRouter(
    prefix="/pdv",
    tags=["PDV"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get(
    "/produtos",
    response_model=list[ProdutoPDV],
)
def pesquisar_produtos(
    q: str,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    return PDVService.pesquisar(
        db,
        q,
        resolver_loja_id(db, usuario, loja_id),
    )


@router.get(
    "/produto/{codigo}",
    response_model=ProdutoPDV,
)
def buscar_produto(
    codigo: str,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    return PDVService.buscar_produto(
        db,
        codigo,
        resolver_loja_id(db, usuario, loja_id),
    )