from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    exigir_permissao,
    get_current_user,
    usuario_tem_permissao,
)
from app.database.session import SessionLocal
from app.schemas.movimento_fiado import (
    FichaFiadoResponse,
    MovimentoFiadoCreate,
    MovimentoFiadoResponse,
    MovimentoFiadoUpdate,
    RegistrarCompraFiadoRequest,
    RegistrarPagamentoFiadoRequest,
    SaldoFiadoResponse,
)
from app.services.movimento_fiado_service import MovimentoFiadoService

router = APIRouter(
    prefix="/fiado",
    tags=["Fiado"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _exigir_permissao_se_abate_sem_dinheiro(db, usuario, dados):
    """HAVER e PAGAMENTO sem forma_pagamento baixam a divida do cliente
    sem entrar dinheiro nenhum no caixa -- na pratica e' um perdao de
    divida, entao so' quem pode corrigir o fiado pode fazer. Pagamento
    de verdade (com forma_pagamento) continua liberado pra qualquer
    operador."""

    tipo = (dados.tipo or "").upper()
    sem_dinheiro = tipo == "HAVER" or (
        tipo == "PAGAMENTO" and not dados.forma_pagamento
    )

    if sem_dinheiro and not usuario_tem_permissao(db, usuario, "fiado.corrigir"):
        raise HTTPException(
            status_code=403,
            detail="Você não tem permissão para realizar essa ação.",
        )


@router.post("/movimentos", response_model=MovimentoFiadoResponse)
def criar_movimento(
    dados: MovimentoFiadoCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    _exigir_permissao_se_abate_sem_dinheiro(db, usuario, dados)

    try:
        movimento = MovimentoFiadoService.criar(
            db,
            dados,
            usuario.id,
        )

        return MovimentoFiadoResponse.from_orm(movimento)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/movimentos", response_model=list[MovimentoFiadoResponse])
def listar_movimentos(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    movimentos = MovimentoFiadoService.listar(db)

    return [
        MovimentoFiadoResponse.from_orm(m)
        for m in movimentos
    ]


@router.get(
    "/movimentos/cliente/{cliente_id}",
    response_model=list[MovimentoFiadoResponse],
)
def listar_por_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    movimentos = MovimentoFiadoService.listar_por_cliente(
        db,
        cliente_id,
    )

    return [
        MovimentoFiadoResponse.from_orm(m)
        for m in movimentos
    ]


@router.put("/movimentos/{movimento_id}")
def atualizar_movimento(
    movimento_id: int,
    dados: MovimentoFiadoUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(exigir_permissao("fiado.corrigir")),
):
    try:
        movimento, caixa_ajustado = MovimentoFiadoService.atualizar(
            db, movimento_id, dados, usuario.id,
        )

        resposta = MovimentoFiadoResponse.from_orm(movimento).dict()
        resposta["caixa_ajustado"] = caixa_ajustado
        return resposta

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/movimentos/{movimento_id}")
def excluir_movimento(
    movimento_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(exigir_permissao("fiado.corrigir")),
):
    try:
        caixa_ajustado = MovimentoFiadoService.excluir(
            db, movimento_id, usuario.id,
        )

        return {
            "success": True,
            "message": "Lançamento excluído com sucesso.",
            "caixa_ajustado": caixa_ajustado,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/saldo/{cliente_id}",
    response_model=SaldoFiadoResponse,
)
def saldo_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    saldo = MovimentoFiadoService.saldo_por_cliente(db, cliente_id)

    return SaldoFiadoResponse(cliente_id=cliente_id, saldo=saldo)


@router.get("/saldos", response_model=dict[int, float])
def saldos_por_cliente(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Saldo devedor de todos os clientes com movimento, numa chamada
    só -- pra listagens (ex.: tela de Clientes) não precisarem de uma
    requisição por cliente."""

    return MovimentoFiadoService.saldos_por_cliente(db)


@router.get("/cliente/{cliente_id}", response_model=FichaFiadoResponse)
def ficha_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return MovimentoFiadoService.ficha_cliente(db, cliente_id)


@router.post(
    "/pagamento",
    response_model=MovimentoFiadoResponse,
    status_code=201,
)
def registrar_pagamento_avulso(
    dados: RegistrarPagamentoFiadoRequest,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Atalho pra registrar um pagamento de fiado sem passar 'tipo' —
    mesma validação e efeitos de POST /fiado/movimentos com
    tipo=PAGAMENTO, só que sem forma_pagamento (não mexe no caixa;
    pra recebimento com impacto no caixa físico, use o endpoint
    genérico de movimentos informando forma_pagamento)."""

    movimento_dados = MovimentoFiadoCreate(
        cliente_id=dados.cliente_id,
        tipo="PAGAMENTO",
        valor=dados.valor,
        descricao=dados.descricao,
        data=dados.data,
    )

    _exigir_permissao_se_abate_sem_dinheiro(db, usuario, movimento_dados)

    movimento = MovimentoFiadoService.criar(db, movimento_dados, usuario.id)

    return MovimentoFiadoResponse.from_orm(movimento)


@router.post(
    "/compra",
    response_model=MovimentoFiadoResponse,
    status_code=201,
)
def registrar_compra_avulsa(
    dados: RegistrarCompraFiadoRequest,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Atalho pra lançar uma compra manual no fiado (ex.: dívida
    migrada da ficha física de papel) sem passar por uma venda do PDV."""

    movimento = MovimentoFiadoService.criar(
        db,
        MovimentoFiadoCreate(
            cliente_id=dados.cliente_id,
            tipo="COMPRA",
            valor=dados.valor,
            descricao=dados.descricao,
            data=dados.data,
        ),
        usuario.id,
    )

    return MovimentoFiadoResponse.from_orm(movimento)
