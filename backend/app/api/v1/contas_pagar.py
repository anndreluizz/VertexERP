from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.database.session import SessionLocal

from app.schemas.conta_pagar import (
    ContaPagarCreate,
    ContaPagarUpdate,
    ContaPagarResponse,
    ContaPagarEventoResponse,
    PagarContaSchema,
    TrocarComprovanteSchema,
)

from app.services.aprovacao_service import AprovacaoService
from app.services.conta_pagar_evento_service import ContaPagarEventoService
from app.services.conta_pagar_service import (
    ContaPagarService,
)
from app.enums.status_conta_pagar import StatusContaPagar

router = APIRouter(
    prefix="/contas-pagar",
    tags=["Contas a Pagar"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=ContaPagarResponse)
def criar(
    dados: ContaPagarCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:

        conta = ContaPagarService.criar(
            db,
            dados,
            usuario_id=usuario.id,
        )

        return ContaPagarResponse.from_orm(conta)

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.get("/", response_model=list[ContaPagarResponse])
def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    contas = ContaPagarService.listar(db, skip, limit)

    return [
        ContaPagarResponse.from_orm(c)
        for c in contas
    ]


@router.get(
    "/pendentes",
    response_model=list[ContaPagarResponse],
)
def listar_pendentes(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    # Sem paginação de propósito: essa lista também alimenta o cálculo
    # do fluxo de caixa (financeiro_service), que precisa do total real.

    contas = ContaPagarService.listar_pendentes(db)

    return [
        ContaPagarResponse.from_orm(c)
        for c in contas
    ]


@router.get(
    "/pagas",
    response_model=list[ContaPagarResponse],
)
def listar_pagas(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    contas = ContaPagarService.listar_pagas(db, skip, limit)

    return [
        ContaPagarResponse.from_orm(c)
        for c in contas
    ]


@router.put(
    "/{conta_id}",
    response_model=ContaPagarResponse,
)
def atualizar(
    conta_id: int,
    dados: ContaPagarUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    try:

        conta = ContaPagarService.atualizar(
            db,
            conta_id,
            dados,
            usuario_id=usuario.id,
        )

        return ContaPagarResponse.from_orm(conta)

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.delete("/{conta_id}")
def excluir(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    try:

        ContaPagarService.excluir(db, conta_id)

        return {
            "success": True,
            "message": "Conta excluída com sucesso.",
        }

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.get("/{conta_id}/documento")
def obter_documento(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    conta = ContaPagarService.buscar_por_id(db, conta_id)

    if not conta or not conta.documento:
        raise HTTPException(
            status_code=404,
            detail="Essa conta não tem documento anexado.",
        )

    nome = conta.documento_nome or "documento"

    return Response(
        content=conta.documento,
        media_type=conta.documento_tipo or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{nome}"',
        },
    )


@router.get("/{conta_id}/comprovante-pagamento")
def obter_comprovante_pagamento(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    conta = ContaPagarService.buscar_por_id(db, conta_id)

    if not conta or not conta.comprovante_pagamento:
        raise HTTPException(
            status_code=404,
            detail="Essa conta não tem comprovante de pagamento anexado.",
        )

    nome = conta.comprovante_pagamento_nome or "comprovante"

    return Response(
        content=conta.comprovante_pagamento,
        media_type=conta.comprovante_pagamento_tipo
        or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{nome}"',
        },
    )


@router.delete("/{conta_id}/documento")
def remover_documento(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        ContaPagarService.remover_documento(db, conta_id)

        return {
            "success": True,
            "message": "Documento removido.",
        }

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.post(
    "/{conta_id}/pagar",
    response_model=ContaPagarResponse,
)
def pagar(
    conta_id: int,
    dados: PagarContaSchema = PagarContaSchema(),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    try:

        conta = ContaPagarService.pagar(
            db,
            conta_id,
            forma_pagamento=dados.forma_pagamento,
            banco_pagamento=dados.banco_pagamento,
            numero_transacao=dados.numero_transacao,
            comprovante_base64=dados.comprovante_base64,
            comprovante_nome=dados.comprovante_nome,
            comprovante_tipo=dados.comprovante_tipo,
            usuario_id=usuario.id,
            dispositivo=dados.dispositivo,
        )

        return ContaPagarResponse.from_orm(conta)

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.put(
    "/{conta_id}/comprovante-pagamento",
    response_model=ContaPagarResponse,
)
def trocar_comprovante(
    conta_id: int,
    dados: TrocarComprovanteSchema,
    db: Session = Depends(get_db),
    usuario=Depends(require_admin),
):

    try:

        conta = ContaPagarService.trocar_comprovante(
            db,
            conta_id,
            comprovante_base64=dados.comprovante_base64,
            comprovante_nome=dados.comprovante_nome,
            comprovante_tipo=dados.comprovante_tipo,
            usuario_id=usuario.id,
            dispositivo=dados.dispositivo,
        )

        return ContaPagarResponse.from_orm(conta)

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.get(
    "/{conta_id}/eventos",
    response_model=list[ContaPagarEventoResponse],
)
def listar_eventos(
    conta_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    eventos = ContaPagarEventoService.listar_por_conta(db, conta_id)

    return [
        ContaPagarEventoResponse(
            id=e.id,
            tipo=e.tipo,
            usuario_id=e.usuario_id,
            usuario_nome=e.usuario_nome,
            dispositivo=e.dispositivo,
            detalhes=e.detalhes,
            data=e.data,
        )
        for e in eventos
    ]


@router.post("/{conta_id}/cancelar")
def cancelar(
    conta_id: int,
    dispositivo: str | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Cancela uma despesa. Pendente: qualquer usuario autenticado
    cancela direto (baixo risco, nenhum dinheiro saiu ainda). Ja paga:
    admin cancela direto; quem nao e admin so consegue pedir -- um
    administrador precisa aprovar pelo celular antes (mesmo padrao ja
    usado pra excluir cliente, ver AprovacaoService). Por isso essa
    rota nao tem response_model fixo: as duas respostas tem formatos
    diferentes de proposito."""

    try:
        conta = ContaPagarService.buscar_por_id(db, conta_id)

        if not conta:
            raise HTTPException(
                status_code=404, detail="Conta não encontrada.",
            )

        if conta.status != StatusContaPagar.PAGO.value or usuario.admin:
            conta = ContaPagarService.cancelar(
                db, conta_id,
                usuario_id=usuario.id, dispositivo=dispositivo,
            )
            return ContaPagarResponse.from_orm(conta)

        AprovacaoService.solicitar(
            db,
            tipo="CANCELAR_CONTA_PAGAR",
            referencia_id=conta_id,
            descricao=(
                f"{usuario.nome} pediu pra cancelar a despesa já paga "
                f"\"{conta.descricao or 'Despesa'}\"."
            ),
            solicitante_id=usuario.id,
        )

        ContaPagarEventoService.registrar(
            db, conta_id, "CANCELAMENTO_SOLICITADO",
            usuario_id=usuario.id, dispositivo=dispositivo,
        )

        return {
            "aprovacao_pendente": True,
            "mensagem": (
                "Pedido enviado — aguardando aprovação de um "
                "administrador."
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))