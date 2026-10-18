import base64
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.auth.dependencies import exigir_financeiro, exigir_permissao, get_current_user, loja_para_leitura, resolver_loja_id
from app.database.session import SessionLocal

from app.schemas.conta_pagar import (
    ContaPagarCreate,
    ContaPagarParceladaCreate,
    LerBoletoRequest,
    LerBoletoResponse,
    ContaPagarUpdate,
    ContaPagarResponse,
    ContaPagarEventoResponse,
    PagarContaSchema,
    TrocarComprovanteSchema,
)

from app.services.aprovacao_service import AprovacaoService
from app.services.conta_pagar_evento_service import ContaPagarEventoService
from app.services.beneficiario_boleto_service import BeneficiarioBoletoService
from app.services.boleto_service import BoletoInvalidoError
from app.services.conta_pagar_service import (
    ContaPagarService,
)
from app.enums.status_conta_pagar import StatusContaPagar

router = APIRouter(
    prefix="/contas-pagar",
    tags=["Contas a Pagar"],
    dependencies=[Depends(exigir_financeiro)],
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
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:

        conta = ContaPagarService.criar(
            db,
            dados,
            usuario_id=usuario.id,
            loja_id=resolver_loja_id(db, usuario, loja_id),
        )

        return ContaPagarResponse.from_orm(conta)

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


@router.post("/ler-boleto", response_model=LerBoletoResponse)
def ler_boleto(
    dados: LerBoletoRequest,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Le o codigo (bipado/digitado) ou o PDF do boleto e devolve
    valor, vencimento, banco, fornecedor (do PDF ou aprendido) e se esse
    boleto ja foi lancado. Nao grava nada."""

    try:
        pdf = base64.b64decode(dados.pdf_base64) if dados.pdf_base64 else None
        return BeneficiarioBoletoService.ler(db, codigo=dados.codigo, pdf=pdf)
    except BoletoInvalidoError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/parcelamento/{parcelamento_id}", response_model=list[ContaPagarResponse])
def listar_parcelamento(
    parcelamento_id: str,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return [
        ContaPagarResponse.from_orm(c)
        for c in ContaPagarService.listar_parcelamento(db, parcelamento_id)
    ]


@router.post("/parcelamento/{parcelamento_id}/cancelar-restantes")
def cancelar_parcelas_restantes(
    parcelamento_id: str,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        quantidade = ContaPagarService.cancelar_parcelas_restantes(
            db, parcelamento_id, usuario_id=usuario.id
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return {"success": True, "canceladas": quantidade}


@router.post("/parcelado", response_model=list[ContaPagarResponse])
def criar_parcelado(
    dados: ContaPagarParceladaCreate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        contas = ContaPagarService.criar_parcelado(
            db,
            dados,
            usuario_id=usuario.id,
            loja_id=resolver_loja_id(db, usuario, loja_id),
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    return [ContaPagarResponse.from_orm(c) for c in contas]


@router.get("/", response_model=list[ContaPagarResponse])
def listar(
    loja_id: int | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    loja_id = loja_para_leitura(usuario, loja_id)

    contas = ContaPagarService.listar(db, skip, limit, loja_id=loja_id)

    return [
        ContaPagarResponse.from_orm(c)
        for c in contas
    ]


@router.get(
    "/pendentes",
    response_model=list[ContaPagarResponse],
)
def listar_pendentes(
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    loja_id = loja_para_leitura(usuario, loja_id)

    contas = ContaPagarService.listar_pendentes(db, loja_id)

    return [
        ContaPagarResponse.from_orm(c)
        for c in contas
    ]


@router.get(
    "/pagas",
    response_model=list[ContaPagarResponse],
)
def listar_pagas(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):

    contas = ContaPagarService.listar_pagas(db)

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
    usuario=Depends(exigir_permissao("contas_pagar.excluir")),
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
    usuario=Depends(get_current_user),
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
