from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, resolver_loja_id, usuario_tem_permissao
from app.database.session import SessionLocal

from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import DashboardService


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get(
    "/",
    response_model=DashboardResponse,
)
def resumo(
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    loja_efetiva = resolver_loja_id(db, usuario, loja_id)
    if usuario_tem_permissao(db, usuario, "financeiro.ver"):
        return DashboardService.resumo(db, loja_efetiva)
    return DashboardService.resumo(db, loja_efetiva, usuario_id=usuario.id)