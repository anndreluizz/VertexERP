from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.user import TrocarSenhaRequest, UserLogin, UserResponse
from app.schemas.refresh_token import RefreshRequest, SessaoResponse
from app.repositories.user_repository import UserRepository
from app.auth.hash import verificar_hash
from app.auth.jwt import criar_token
from app.auth.dependencies import get_current_user
from app.services.auth_service import AuthService
from app.services.user_service import UserService

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


@router.post("/login")
def login(
    dados: UserLogin,
    db: Session = Depends(get_db)
):

    usuario = UserRepository.buscar_por_email(
        db,
        dados.email
    )

    if not usuario:
        raise HTTPException(
            status_code=401,
            detail="Usuário inválido."
        )

    if not verificar_hash(
        dados.senha,
        usuario.senha
    ):
        raise HTTPException(
            status_code=401,
            detail="Senha inválida."
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=403,
            detail="Usuário desativado. Fale com um administrador.",
        )

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
        db, usuario.id, dispositivo=dados.dispositivo
    )

    return {
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


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
