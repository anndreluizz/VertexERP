from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_admin
from app.core.responses import ApiResponse
from app.database.session import SessionLocal
from app.schemas.user import (
    UserAdminUpdate,
    UserAtivoUpdate,
    UserCreate,
    UserResponse,
)
from app.services.user_service import UserService

router = APIRouter(
    prefix="/users",
    tags=["Usuários"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/")
def criar_usuario(
    dados: UserCreate,
    db: Session = Depends(get_db),
    usuario_logado=Depends(require_admin),
):
    usuario = UserService.criar_usuario(db, dados)

    return ApiResponse.success(
        data=UserResponse.from_orm(usuario).dict(),
        message="Usuário cadastrado com sucesso.",
    )


@router.get("/")
def listar_usuarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    usuarios = UserService.listar_usuarios(db, skip, limit)

    return ApiResponse.success(
        data=[
            UserResponse.from_orm(u).dict()
            for u in usuarios
        ],
        message="Usuários listados com sucesso.",
    )


@router.get("/me")
def meu_perfil(
    usuario=Depends(get_current_user),
):
    return ApiResponse.success(
        data=UserResponse.from_orm(usuario).dict(),
        message="Perfil carregado com sucesso.",
    )


@router.put("/{user_id}/admin")
def definir_admin(
    user_id: int,
    dados: UserAdminUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(require_admin),
):
    usuario_alvo = UserService.definir_admin(db, user_id, dados.admin)

    return ApiResponse.success(
        data=UserResponse.from_orm(usuario_alvo).dict(),
        message="Permissão atualizada com sucesso.",
    )


@router.put("/{user_id}/ativo")
def definir_ativo(
    user_id: int,
    dados: UserAtivoUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(require_admin),
):
    usuario_alvo = UserService.definir_ativo(db, user_id, dados.ativo)

    return ApiResponse.success(
        data=UserResponse.from_orm(usuario_alvo).dict(),
        message="Status atualizado com sucesso.",
    )