from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.database.session import SessionLocal
from app.schemas.configuracao import (
    ConfiguracaoResponse,
    ConfiguracaoUpdate,
)
from app.services.configuracao_service import ConfiguracaoService

router = APIRouter(
    prefix="/configuracoes",
    tags=["Configurações"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=ConfiguracaoResponse)
def buscar_configuracoes(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return ConfiguracaoService.buscar(db)


@router.put("/", response_model=ConfiguracaoResponse)
def atualizar_configuracoes(
    dados: ConfiguracaoUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(require_admin),
):
    return ConfiguracaoService.atualizar(db, dados)


@router.post("/logo", response_model=ConfiguracaoResponse)
async def enviar_logo(
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario=Depends(require_admin),
):
    conteudo = await arquivo.read()

    return ConfiguracaoService.salvar_logo(db, arquivo.filename, conteudo)


@router.get("/logo")
def buscar_logo(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    caminho = ConfiguracaoService.caminho_logo(db)

    if caminho is None:
        raise Exception("Nenhuma logo cadastrada.")

    return FileResponse(caminho)
