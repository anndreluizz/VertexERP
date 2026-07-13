from jose import jwt
from datetime import datetime, timedelta

SECRET_KEY = "VERTEXERP2026SECRET"

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60


def criar_token(data: dict):

    dados = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    dados.update({"exp": expire})

    return jwt.encode(
        dados,
        SECRET_KEY,
        algorithm=ALGORITHM
    )