from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.cliente import (
    ClienteCreate,
    ClienteUpdate,
    ClienteResponse,
    ClienteObservacaoCreate,
    ClienteObservacaoResponse,
)
from app.services.cliente_service import ClienteService
from app.services.cliente_observacao_service import ClienteObservacaoService
from app.services.aprovacao_service import AprovacaoService
from app.auth.dependencies import get_current_user

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
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    try:
        return ClienteService.criar(db, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[ClienteResponse])
def listar_clientes(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user)
):
    return ClienteService.listar(db)


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
        return ClienteObservacaoService.excluir(db, observacao_id)
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
