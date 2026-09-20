from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, resolver_loja_id
from app.database.session import SessionLocal
from app.schemas.transacao_bancaria import (
    OfxImportarRequest,
    OfxPreviewResponse,
    OfxImportarResultado,
    TransacaoBancariaResponse,
    ConciliarRequest,
    CandidatoConciliacao,
)
from app.services.extrato_bancario_service import ExtratoBancarioService

router = APIRouter(
    prefix="/extrato-bancario",
    tags=["Extrato Bancário"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/preview", response_model=OfxPreviewResponse)
def preview(
    dados: OfxImportarRequest,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """So' leitura -- extrai e marca o que ja foi importado, nao grava
    nada. Confirmar de verdade e' POST /extrato-bancario/importar."""
    try:
        return ExtratoBancarioService.pre_visualizar(
            db, dados.ofx_conteudo, resolver_loja_id(db, usuario, loja_id)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/importar", response_model=OfxImportarResultado)
def importar(
    dados: OfxImportarRequest,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        total = ExtratoBancarioService.importar(
            db, dados.ofx_conteudo, resolver_loja_id(db, usuario, loja_id)
        )
        return OfxImportarResultado(total_importadas=total)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[TransacaoBancariaResponse])
def listar(
    status: str | None = Query(None),
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return ExtratoBancarioService.listar(
        db, resolver_loja_id(db, usuario, loja_id), status
    )


@router.get(
    "/{transacao_id}/sugestoes", response_model=list[CandidatoConciliacao]
)
def sugestoes(
    transacao_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return ExtratoBancarioService.sugerir_candidatos(db, transacao_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{transacao_id}/conciliar", response_model=TransacaoBancariaResponse
)
def conciliar(
    transacao_id: int,
    dados: ConciliarRequest,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return ExtratoBancarioService.conciliar(
            db,
            transacao_id,
            dados.conta_pagar_id,
            dados.conta_receber_id,
            usuario.id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{transacao_id}/desconciliar", response_model=TransacaoBancariaResponse
)
def desconciliar(
    transacao_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return ExtratoBancarioService.desconciliar(db, transacao_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/{transacao_id}/ignorar", response_model=TransacaoBancariaResponse
)
def ignorar(
    transacao_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return ExtratoBancarioService.ignorar(db, transacao_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
