from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.core.responses import ApiResponse
from app.database.session import SessionLocal
from app.schemas.user import UserCreate, UserResponse
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
):
    usuario = UserService.criar_usuario(db, dados)

    return ApiResponse.success(
        data=UserResponse.model_validate(usuario).model_dump(),
        message="Usuário cadastrado com sucesso.",
    )


@router.get("/")
def listar_usuarios(
    db: Session = Depends(get_db),
    usuario=Depends(get_current_user),
):
    usuarios = UserService.listar_usuarios(db)

    return ApiResponse.success(
        data=[
            UserResponse.model_validate(u).model_dump()
            for u in usuarios
        ],
        message="Usuários listados com sucesso.",
    )