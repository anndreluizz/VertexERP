from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.schemas.device_token import DeviceTokenCreate
from app.schemas.notificacao import ContagemNaoLidasResponse, NotificacaoResponse
from app.services.device_token_service import DeviceTokenService
from app.repositories.notificacao_repository import NotificacaoRepository

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


@router.get("/", response_model=list[NotificacaoResponse])
def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return NotificacaoRepository.listar(db, usuario.id, skip, limit)


@router.get("/nao-lidas", response_model=ContagemNaoLidasResponse)
def contagem_nao_lidas(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return {
        "nao_lidas": NotificacaoRepository.contar_nao_lidas(db, usuario.id)
    }


@router.post("/{notificacao_id}/marcar-lida")
def marcar_lida(
    notificacao_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    notificacao = NotificacaoRepository.buscar_por_id(
        db, notificacao_id, usuario.id
    )

    if notificacao is None:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")

    notificacao.lida = True
    NotificacaoRepository.salvar(db)

    return {"success": True}


@router.post("/marcar-todas-lidas")
def marcar_todas_lidas(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    NotificacaoRepository.marcar_todas_lidas(db, usuario.id)

    return {"success": True}


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
