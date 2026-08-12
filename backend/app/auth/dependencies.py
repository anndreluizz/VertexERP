from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.auth.jwt import SECRET_KEY, ALGORITHM
from app.database.session import SessionLocal
from app.models.user import User

security = HTTPBearer()


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

        return usuario

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Token inválido."
        )


def require_admin(
    usuario: User = Depends(get_current_user),
) -> User:

    if not usuario.admin:
        raise HTTPException(
            status_code=403,
            detail="Apenas administradores podem realizar esta ação."
        )

    return usuario