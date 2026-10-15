from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, exigir_permissao, loja_para_leitura, resolver_loja_id
from app.database.session import SessionLocal
from app.models.caixa import Caixa
from app.models.user import User
from app.schemas.caixa import (
    CaixaCreate,
    CaixaResponse,
    EntradasCaixaResponse,
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
        valor_guardado=caixa.valor_guardado,
        valor_retirado=caixa.valor_retirado,
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
            valor_guardado=dados.valor_guardado,
            valor_retirado=dados.valor_retirado,
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
    limite: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    loja_id = loja_para_leitura(usuario, loja_id)
    caixas = CaixaService.historico(db, limite=limite, loja_id=loja_id)

    nomes = dict(db.query(User.id, User.nome).filter(
        User.id.in_({c.usuario_id for c in caixas if c.usuario_id})
    ).all())

    respostas = []
    for c in caixas:
        resposta = caixa_to_response(c)
        resposta.usuario_nome = nomes.get(c.usuario_id)
        respostas.append(resposta)
    return respostas


@router.get("/entradas", response_model=EntradasCaixaResponse)
def entradas_caixa(
    inicio: date | None = None,
    fim: date | None = None,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Quanto entrou de verdade no periodo, somando todos os caixas
    (Relatorios > Caixa)."""
    loja_id = loja_para_leitura(usuario, loja_id)
    return CaixaService.entradas(db, inicio, fim, loja_id)


@router.get("/{caixa_id}/resumo", response_model=ResumoCaixaResponse)
def resumo_caixa_por_id(
    caixa_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Resumo de qualquer caixa (inclusive já fechado) -- tela Caixas
    anteriores / reimprimir fechamento."""

    caixa = db.get(Caixa, caixa_id)
    loja_permitida = loja_para_leitura(usuario)

    if caixa is None or (loja_permitida is not None and caixa.loja_id != loja_permitida):
        raise HTTPException(status_code=404, detail="Caixa não encontrado.")

    return CaixaService.resumo(db, caixa)
