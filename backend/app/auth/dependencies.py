from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.auth.jwt import SECRET_KEY, ALGORITHM
from app.database.session import SessionLocal
from app.models.user import User

security = HTTPBearer()
security_opcional = HTTPBearer(auto_error=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials

    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("id")

        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Token inválido."
            )

        usuario = (
            db.query(User)
            .filter(User.id == user_id)
            .first()
        )

        if usuario is None:
            raise HTTPException(
                status_code=401,
                detail="Usuário não encontrado."
            )

        if not usuario.ativo:
            raise HTTPException(
                status_code=403,
                detail="Usuário desativado.",
            )

        return usuario

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token inválido."
        )


def get_current_admin(
    usuario: User = Depends(get_current_user),
):
    if not usuario.admin:
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores podem realizar essa ação.",
        )

    return usuario


def exigir_admin_apos_primeiro_usuario(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        security_opcional
    ),
    db: Session = Depends(get_db),
):
    """Cadastro de usuário (POST /users/) só pode ficar aberto sem login
    enquanto a loja não tiver ninguém cadastrado ainda — é a tela
    "Comece Grátis" do primeiro acesso. A partir do segundo usuário em
    diante, exige um admin autenticado; sem essa checagem, qualquer um
    com acesso à rede do backend conseguia criar contas à vontade."""

    if db.query(User).count() == 0:
        return None

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Autenticação necessária.",
        )

    usuario = get_current_user(credentials, db)

    if not usuario.admin:
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores podem cadastrar novos usuários.",
        )

    return usuario