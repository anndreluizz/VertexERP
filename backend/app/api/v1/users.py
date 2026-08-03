from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_current_user,
    get_current_admin,
    exigir_admin_apos_primeiro_usuario,
)
from app.core.responses import ApiResponse
from app.database.session import SessionLocal
from app.schemas.user import UserCreate, UserUpdate, UserResponse
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


@router.get("/existe")
def existe_usuario(
    db: Session = Depends(get_db),
):
    return ApiResponse.success(
        data={"existe": UserService.existe_usuario(db)},
        message="Verificação concluída.",
    )


@router.post("/")
def criar_usuario(
    dados: UserCreate,
    db: Session = Depends(get_db),
    _autorizacao=Depends(exigir_admin_apos_primeiro_usuario),
):
    try:
        usuario = UserService.criar_usuario(db, dados)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ApiResponse.success(
        data=UserResponse.from_orm(usuario).dict(),
        message="Usuário cadastrado com sucesso.",
    )


@router.get("/")
def listar_usuarios(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_admin),
):
    usuarios = UserService.listar_usuarios(db)

    return ApiResponse.success(
        data=[
            UserResponse.from_orm(u).dict()
            for u in usuarios
        ],
        message="Usuários listados com sucesso.",
    )


@router.put("/{user_id}")
def atualizar_usuario(
    user_id: int,
    dados: UserUpdate,
    db: Session = Depends(get_db),
    usuario=Depends(get_current_admin),
):
    try:
        atualizado = UserService.atualizar(db, user_id, dados, usuario)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ApiResponse.success(
        data=UserResponse.from_orm(atualizado).dict(),
        message="Usuário atualizado com sucesso.",
    )
