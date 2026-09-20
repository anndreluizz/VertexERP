import base64

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import exigir_permissao, get_current_user, resolver_loja_id
from app.database.session import SessionLocal
from app.models.cliente import Cliente
from app.schemas.venda import (
    VendaCreate,
    VendaResponse,
    ComprovanteVendaResponse,
    ComprovanteEnvioResponse,
    ComprovanteEnviarWhatsappRequest,
    ComprovanteEnviarEmailRequest,
)
from app.services.venda_service import VendaService
from app.services.comprovante_envio_service import ComprovanteEnvioService
from app.services.whatsapp_service import WhatsappService
from app.services.email_service import EmailService

router = APIRouter(
    prefix="/vendas",
    tags=["Vendas"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=list[VendaResponse])
def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return VendaService.listar(db, skip, limit, loja_id)


@router.get("/{venda_id}", response_model=VendaResponse)
def buscar(
    venda_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    venda = VendaService.buscar(db, venda_id)

    if not venda:
        raise HTTPException(
            status_code=404,
            detail="Venda não encontrada"
        )

    return venda


@router.post("/", response_model=VendaResponse, status_code=201)
def criar(
    dados: VendaCreate,
    loja_id: int | None = None,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        loja_efetiva = resolver_loja_id(db, usuario, loja_id)
        return VendaService.criar(db, dados, usuario.id, loja_efetiva)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{venda_id}")
def excluir(
    venda_id: int,
    motivo: str | None = Query(None, max_length=255),
    db: Session = Depends(get_db),
    usuario=Depends(exigir_permissao("vendas.cancelar")),
):

    try:
        ok = VendaService.excluir(db, venda_id, usuario.id, motivo)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Venda não encontrada"
        )

    return {
        "success": True,
        "message": "Venda cancelada com sucesso."
    }


# ==================================================
# COMPROVANTE
# ==================================================


@router.get(
    "/{venda_id}/comprovante",
    response_model=ComprovanteVendaResponse,
)
def obter_comprovante(
    venda_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        return VendaService.montar_comprovante(db, venda_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/{venda_id}/comprovante-envios",
    response_model=list[ComprovanteEnvioResponse],
)
def listar_envios_comprovante(
    venda_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    envios = ComprovanteEnvioService.listar_por_venda(db, venda_id)

    return [
        ComprovanteEnvioResponse(
            id=e.id,
            canal=e.canal,
            destino=e.destino,
            status=e.status,
            erro=e.erro,
            usuario_id=e.usuario_id,
            usuario_nome=e.usuario_nome,
            data=e.data,
        )
        for e in envios
    ]


@router.post("/{venda_id}/comprovante/whatsapp")
def enviar_comprovante_whatsapp(
    venda_id: int,
    dados: ComprovanteEnviarWhatsappRequest,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    venda = VendaService.buscar(db, venda_id)

    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada.")

    cliente = (
        db.query(Cliente).filter(Cliente.id == venda.cliente_id).first()
        if venda.cliente_id else None
    )

    telefone = cliente.telefone if cliente else None

    sucesso, erro = WhatsappService.enviar_documento(
        db,
        telefone,
        dados.pdf_base64,
        dados.nome_arquivo,
        dados.legenda,
    )

    ComprovanteEnvioService.registrar(
        db,
        venda_id=venda_id,
        canal="WHATSAPP",
        destino=telefone or "—",
        status="ENVIADO" if sucesso else "FALHOU",
        usuario_id=usuario.id,
        erro=erro,
    )

    if not sucesso:
        raise HTTPException(status_code=400, detail=erro)

    return {"success": True, "message": "Comprovante enviado pelo WhatsApp."}


@router.post("/{venda_id}/comprovante/email")
def enviar_comprovante_email(
    venda_id: int,
    dados: ComprovanteEnviarEmailRequest,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    venda = VendaService.buscar(db, venda_id)

    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada.")

    cliente = (
        db.query(Cliente).filter(Cliente.id == venda.cliente_id).first()
        if venda.cliente_id else None
    )

    destinatario = dados.destinatario or (cliente.email if cliente else None)

    anexo_bytes = base64.b64decode(dados.pdf_base64)

    sucesso, erro = EmailService.enviar_email(
        db,
        destinatario,
        dados.assunto,
        dados.corpo,
        anexo_bytes,
        dados.nome_arquivo,
    )

    ComprovanteEnvioService.registrar(
        db,
        venda_id=venda_id,
        canal="EMAIL",
        destino=destinatario or "—",
        status="ENVIADO" if sucesso else "FALHOU",
        usuario_id=usuario.id,
        erro=erro,
    )

    if not sucesso:
        raise HTTPException(status_code=400, detail=erro)

    return {"success": True, "message": "Comprovante enviado por e-mail."}
