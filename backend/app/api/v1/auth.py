from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.user import (
    TrocarSenhaRequest,
    UserLogin,
    UserResponse,
    Verificar2FARequest,
)
from app.schemas.refresh_token import RefreshRequest, SessaoResponse
from app.repositories.user_repository import UserRepository
from app.auth.hash import verificar_hash
from app.auth.jwt import criar_token
from app.auth.dependencies import get_current_user
from app.auth import rate_limit, dois_fatores
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.services.email_service import EmailService

router = APIRouter(
    prefix="/auth",
    tags=["Autenticação"]
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _emitir_tokens(db: Session, usuario, dispositivo: str | None):
    """Access token + refresh token de uma sessao autenticada -- usado
    tanto pelo login sem 2FA quanto pelo /auth/verificar-2fa (2o passo
    de quem tem 2FA ativo), pra nao duplicar essa parte nos dois."""

    token = criar_token(
        {
            "sub": usuario.email,
            "id": usuario.id
        }
    )

    # Sessao de longa duracao (90 dias), revogavel a qualquer momento
    # (ver /auth/sessoes) -- o access_token acima sozinho nunca teria
    # como ser "deslogado remotamente", ja que fica valido ate expirar
    # naturalmente sem nenhum jeito de invalidar antes disso.
    refresh_token = AuthService.gerar_refresh_token(
        db, usuario.id, dispositivo=dispositivo
    )

    return {
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/login")
def login(
    dados: UserLogin,
    db: Session = Depends(get_db)
):

    # checa o bloqueio ANTES de tocar no banco/hash -- nem vale a pena
    # gastar o custo do bcrypt numa tentativa que já vai ser recusada
    espera = rate_limit.segundos_ate_desbloquear(dados.email)

    if espera:
        minutos = max(1, espera // 60)
        raise HTTPException(
            status_code=429,
            detail=(
                "Muitas tentativas com senha errada. "
                f"Tente novamente em {minutos} minuto(s)."
            ),
        )

    usuario = UserRepository.buscar_por_email(
        db,
        dados.email
    )

    if not usuario:
        rate_limit.registrar_falha(dados.email)
        raise HTTPException(
            status_code=401,
            detail="Usuário inválido."
        )

    if not verificar_hash(
        dados.senha,
        usuario.senha
    ):
        rate_limit.registrar_falha(dados.email)
        raise HTTPException(
            status_code=401,
            detail="Senha inválida."
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=403,
            detail="Usuário desativado. Fale com um administrador.",
        )

    rate_limit.limpar(dados.email)

    # 2FA ativo: nao devolve os tokens ainda -- manda um codigo por
    # e-mail e devolve so o verificacao_id, que o cliente troca pelos
    # tokens de verdade em /auth/verificar-2fa (ver funcao abaixo).
    if usuario.dois_fatores_ativo:

        verificacao_id, codigo = dois_fatores.criar_pendente(usuario.id)

        enviado, erro = EmailService.enviar_email(
            db,
            usuario.email,
            "Codigo de verificacao - Vertex ERP",
            (
                f"Seu codigo de verificacao e: {codigo}\n\n"
                "Ele vale por 10 minutos. Se voce nao tentou entrar "
                "no Vertex ERP agora, ignore este e-mail."
            ),
        )

        if not enviado:
            # falha fechada de proposito: sem conseguir mandar o
            # codigo, ninguem consegue provar o segundo fator -- nao
            # da pra simplesmente deixar passar sem o 2FA (anularia o
            # sentido dele). Um admin pode desativar o 2FA desse
            # usuario em Gerenciar Usuarios como via de escape.
            raise HTTPException(
                status_code=503,
                detail=(
                    "Não foi possível enviar o código de verificação "
                    f"por e-mail ({erro}). Fale com um administrador."
                ),
            )

        return {
            "requer_2fa": True,
            "verificacao_id": verificacao_id,
        }

    return _emitir_tokens(db, usuario, dados.dispositivo)


@router.post("/verificar-2fa")
def verificar_2fa(
    dados: Verificar2FARequest,
    db: Session = Depends(get_db),
):
    """2o passo do login pra quem tem 2FA ativo -- troca o
    verificacao_id + codigo (recebido por e-mail) pelos tokens de
    verdade, do mesmo jeito que o /auth/login normal devolveria."""

    usuario_id = dois_fatores.verificar(dados.verificacao_id, dados.codigo)

    if not usuario_id:
        raise HTTPException(
            status_code=401,
            detail="Código inválido ou expirado. Faça login novamente.",
        )

    usuario = UserRepository.buscar_por_id(db, usuario_id)

    if not usuario or not usuario.ativo:
        raise HTTPException(
            status_code=401,
            detail="Usuário inválido ou desativado.",
        )

    return _emitir_tokens(db, usuario, dados.dispositivo)


@router.post("/refresh")
def refresh(
    dados: RefreshRequest,
    db: Session = Depends(get_db),
):
    sessao = AuthService.validar_refresh_token(db, dados.refresh_token)

    if not sessao:
        raise HTTPException(
            status_code=401,
            detail="Sessão expirada ou encerrada. Faça login novamente.",
        )

    usuario = UserRepository.buscar_por_id(db, sessao.usuario_id)

    if not usuario or not usuario.ativo:
        raise HTTPException(
            status_code=401,
            detail="Usuário inválido ou desativado.",
        )

    novo_access_token = criar_token(
        {
            "sub": usuario.email,
            "id": usuario.id
        }
    )

    return {
        "access_token": novo_access_token,
        "token_type": "bearer",
    }


@router.get("/sessoes", response_model=list[SessaoResponse])
def listar_sessoes(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    return AuthService.listar_sessoes(db, usuario.id)


@router.delete("/sessoes/{sessao_id}")
def revogar_sessao(
    sessao_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        AuthService.revogar_sessao(db, usuario.id, sessao_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "success": True,
        "message": "Sessão encerrada.",
    }


@router.get("/me", response_model=UserResponse)
def me(
    usuario=Depends(get_current_user),
):
    return UserResponse.from_orm(usuario)


@router.put("/senha")
def trocar_senha(
    dados: TrocarSenhaRequest,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    try:
        UserService.trocar_senha(
            db, usuario, dados.senha_atual, dados.senha_nova
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": "Senha alterada com sucesso.",
    }
