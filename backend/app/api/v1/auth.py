from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.schemas.user import UserLogin, UserResponse
from app.repositories.user_repository import UserRepository
from app.auth.hash import verificar_hash
from app.auth.jwt import criar_token
from app.auth.dependencies import get_current_user

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

    return {
        "access_token": token,
        "token_type": "bearer"
    }


@router.get("/me", response_model=UserResponse)
def me(
    usuario=Depends(get_current_user),
):
    return UserResponse.from_orm(usuario)