from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.schemas.device_token import DeviceTokenCreate
from app.services.device_token_service import DeviceTokenService

router = APIRouter(
    prefix="/notificacoes",
    tags=["Notificações"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/registrar-token")
def registrar_token(
    dados: DeviceTokenCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    DeviceTokenService.registrar(db, dados, usuario.id)

    return {
        "success": True,
        "message": "Token registrado com sucesso.",
    }


@router.delete("/token/{token}")
def remover_token(
    token: str,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    DeviceTokenService.remover(db, token, usuario.id)

    return {
        "success": True,
        "message": "Token removido com sucesso.",
    }
