from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.schemas.financeiro import FluxoCaixaResponse
from app.services.financeiro_service import FinanceiroService

router = APIRouter(
    prefix="/financeiro",
    tags=["Financeiro"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/fluxo-caixa", response_model=FluxoCaixaResponse)
def fluxo_caixa(
    dias: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return FinanceiroService.fluxo_caixa(db, dias)
