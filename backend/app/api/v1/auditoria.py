from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.database.session import SessionLocal
from app.schemas.log_auditoria import LogAuditoriaResponse
from app.services.log_auditoria_service import LogAuditoriaService

router = APIRouter(
    prefix="/auditoria",
    tags=["Auditoria"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=list[LogAuditoriaResponse])
def listar(
    usuario_id: int | None = None,
    acao: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_admin),
):
    return LogAuditoriaService.listar(db, usuario_id, acao, skip, limit)
