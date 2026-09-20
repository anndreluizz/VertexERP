from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.cliente import (
    ClienteCreate,
    ClienteUpdate,
    ClienteResponse,
    ClienteEnviarWhatsappRequest,
    ClienteObservacaoCreate,
    ClienteObservacaoResponse,
    ClienteDadosLgpdResponse,
    ClienteAnonimizadoResponse,
)
from app.services.cliente_service import ClienteService
from app.services.cliente_observacao_service import ClienteObservacaoService
from app.services.aprovacao_service import AprovacaoService
from app.services.whatsapp_service import WhatsappService
from app.auth.dependencies import get_current_user, exigir_permissao, resolver_loja_id

router = APIRouter(
    prefix="/clientes",
    tags=["Clientes"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/", response_model=ClienteResponse)
def criar_cliente(
    dados: ClienteCreate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    try:
        return ClienteService.criar(
            db, dados, resolver_loja_id(db, usuario, loja_id)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[ClienteResponse])
def listar_clientes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    return ClienteService.listar(db, skip, limit, loja_id)


@router.get("/{cliente_id}", response_model=ClienteResponse)
def buscar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    cliente = ClienteService.buscar_por_id(db, cliente_id)

    if not cliente:
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado.",
        )

    return cliente


@router.get("/{cliente_id}/foto")
def obter_foto_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    cliente = ClienteService.buscar_por_id(db, cliente_id)

    if not cliente or not cliente.foto:
        raise HTTPException(
            status_code=404,
            detail="Cliente sem foto cadastrada."
        )

    return Response(content=cliente.foto, media_type="image/jpeg")


@router.post("/{cliente_id}/whatsapp")
def enviar_whatsapp_texto(
    cliente_id: int,
    dados: ClienteEnviarWhatsappRequest,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    """Manda uma mensagem de texto livre pro cliente via WhatsApp --
    usado pelos itens do menu 'WhatsApp ▾' da ficha do cliente (extrato
    completo, cobrança, saldo devedor, haver, cadastro). Ao contrário
    do comprovante de venda, não fica registrado em historico_envios
    (esse historico e' especifico de venda/comprovante) -- se falhar,
    quem chamou (frontend) decide se abre o wa.me manual como plano B."""

    cliente = ClienteService.buscar_por_id(db, cliente_id)

    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")

    sucesso = WhatsappService.enviar_mensagem(db, cliente.telefone, dados.texto)

    if not sucesso:
        raise HTTPException(
            status_code=400,
            detail="Não foi possível enviar a mensagem pelo WhatsApp.",
        )

    return {"success": True, "message": "Mensagem enviada pelo WhatsApp."}


@router.get(
    "/{cliente_id}/observacoes",
    response_model=list[ClienteObservacaoResponse],
)
def listar_observacoes(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return ClienteObservacaoService.listar(db, cliente_id)


@router.post(
    "/{cliente_id}/observacoes",
    response_model=ClienteObservacaoResponse,
)
def criar_observacao(
    cliente_id: int,
    dados: ClienteObservacaoCreate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return ClienteObservacaoService.criar(
            db, cliente_id, dados, usuario.id
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{cliente_id}/observacoes/{observacao_id}")
def excluir_observacao(
    cliente_id: int,
    observacao_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return ClienteObservacaoService.excluir(db, cliente_id, observacao_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{cliente_id}", response_model=ClienteResponse)
def atualizar_cliente(
    cliente_id: int,
    dados: ClienteUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    try:
        return ClienteService.atualizar(
            db,
            cliente_id,
            dados
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{cliente_id}")
def excluir_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    try:
        # Admin exclui direto, igual sempre foi. Quem nao e admin so
        # consegue pedir — um administrador precisa aprovar pelo
        # celular antes do cliente ser desativado de verdade.
        if usuario.admin:
            return ClienteService.excluir(db, cliente_id)

        cliente = ClienteService.buscar_por_id(db, cliente_id)

        if not cliente:
            raise Exception("Cliente não encontrado.")

        AprovacaoService.solicitar(
            db,
            tipo="EXCLUIR_CLIENTE",
            referencia_id=cliente_id,
            descricao=(
                f"{usuario.nome} pediu pra excluir o cliente "
                f"\"{cliente.nome}\"."
            ),
            solicitante_id=usuario.id,
        )

        return {
            "aprovacao_pendente": True,
            "mensagem": (
                "Pedido enviado — aguardando aprovação de um "
                "administrador."
            ),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{cliente_id}/reativar")
def reativar_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    # reativar e' de baixo risco (o oposto de excluir) -- nao precisa
    # do fluxo de aprovacao, qualquer usuario autenticado resolve.
    try:
        return ClienteService.reativar(db, cliente_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.get("/{cliente_id}/dados-lgpd", response_model=ClienteDadosLgpdResponse)
def exportar_dados_lgpd(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(exigir_permissao("clientes.lgpd")),
):
    """Todos os dados pessoais guardados sobre o cliente, numa
    resposta só -- atende um pedido de acesso/portabilidade (LGPD,
    Lei 13.709/2018, art. 18, II). Só admin, é um relatório completo
    de dados pessoais sensíveis."""

    try:
        return ClienteService.exportar_dados_lgpd(db, cliente_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{cliente_id}/dados-lgpd", response_model=ClienteAnonimizadoResponse)
def remover_dados_lgpd(
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(exigir_permissao("clientes.lgpd")),
):
    """Direito ao esquecimento (LGPD, art. 18, VI) -- apaga os dados
    pessoais do cliente, mantendo vendas/fiado no histórico contábil
    (ver ClienteService.anonimizar_dados_lgpd pro porquê). Ação
    irreversível, por isso só admin."""

    try:
        return ClienteService.anonimizar_dados_lgpd(db, cliente_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
