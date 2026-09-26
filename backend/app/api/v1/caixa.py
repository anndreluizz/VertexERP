from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, exigir_permissao, loja_para_leitura, resolver_loja_id
from app.database.session import SessionLocal
from app.schemas.caixa import (
    CaixaCreate,
    CaixaResponse,
    FecharCaixaRequest,
    ResumoCaixaResponse,
)
from app.services.caixa_service import CaixaService

router = APIRouter(
    prefix="/caixa",
    tags=["Caixa"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def caixa_to_response(caixa):
    if caixa is None:
        return None

    return CaixaResponse(
        id=caixa.id,
        data_abertura=caixa.data_abertura,
        data_fechamento=caixa.data_fechamento,
        saldo_inicial=caixa.saldo_inicial,
        saldo_final=caixa.saldo_final,
        status=caixa.status,
        valor_contado=caixa.valor_contado,
        observacoes=caixa.observacoes,
        usuario_id=caixa.usuario_id,
    )


@router.post("/abrir", response_model=CaixaResponse)
def abrir_caixa(
    dados: CaixaCreate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        loja_efetiva = resolver_loja_id(db, usuario, loja_id)
        caixa = CaixaService.abrir(db, dados, usuario.id, loja_efetiva)
        return caixa_to_response(caixa)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fechar", response_model=CaixaResponse)
def fechar_caixa(
    dados: FecharCaixaRequest,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(exigir_permissao("caixa.fechar")),
):
    try:
        loja_efetiva = resolver_loja_id(db, usuario, loja_id)
        caixa = CaixaService.fechar(
            db,
            usuario.id,
            dados.valor_contado,
            dados.observacoes,
            loja_efetiva,
        )
        return caixa_to_response(caixa)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/aberto", response_model=CaixaResponse | None)
def caixa_aberto(
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    loja_efetiva = resolver_loja_id(db, usuario, loja_id)
    caixa = CaixaService.caixa_aberto(db, usuario.id, loja_efetiva)

    if caixa is None:
        return None

    return caixa_to_response(caixa)


@router.get("/resumo", response_model=ResumoCaixaResponse)
def resumo_caixa(
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    loja_efetiva = resolver_loja_id(db, usuario, loja_id)
    resumo = CaixaService.resumo_aberto(db, usuario.id, loja_efetiva)

    if resumo is None:
        raise HTTPException(
            status_code=400,
            detail="Nenhum caixa aberto.",
        )

    return resumo


@router.get("/historico", response_model=list[CaixaResponse])
def historico_caixa(
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    loja_id = loja_para_leitura(usuario, loja_id)
    caixas = CaixaService.historico(db, loja_id=loja_id)

    return [caixa_to_response(c) for c in caixas]
