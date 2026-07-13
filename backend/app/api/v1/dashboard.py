from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
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
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return DashboardService.resumo(db)