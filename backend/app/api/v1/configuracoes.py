from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.schemas.configuracao import ConfiguracaoResponse, ConfiguracaoUpdate
from app.services.configuracao_service import ConfiguracaoService

router = APIRouter(
    prefix="/configuracoes",
    tags=["Configurações"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=ConfiguracaoResponse)
def buscar_configuracao(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    return ConfiguracaoService.buscar(db)


@router.put("/", response_model=ConfiguracaoResponse)
def atualizar_configuracao(
    dados: ConfiguracaoUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    return ConfiguracaoService.atualizar(db, dados)
