from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin
from app.database.session import SessionLocal
from app.schemas.solicitacao_aprovacao import SolicitacaoAprovacaoResponse
from app.services.aprovacao_service import AprovacaoService

router = APIRouter(
    prefix="/aprovacoes",
    tags=["Aprovações"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get(
    "/pendentes",
    response_model=list[SolicitacaoAprovacaoResponse],
)
def listar_pendentes(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_admin),
):
    return AprovacaoService.listar_pendentes(db)


@router.post(
    "/{solicitacao_id}/aprovar",
    response_model=SolicitacaoAprovacaoResponse,
)
def aprovar(
    solicitacao_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_admin),
):
    try:
        return AprovacaoService.aprovar(db, solicitacao_id, usuario.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{solicitacao_id}/rejeitar",
    response_model=SolicitacaoAprovacaoResponse,
)
def rejeitar(
    solicitacao_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_admin),
):
    try:
        return AprovacaoService.rejeitar(db, solicitacao_id, usuario.id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
