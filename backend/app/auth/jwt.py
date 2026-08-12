import os

from jose import jwt
from datetime import datetime, timedelta

# Cai pro literal antigo só quando não há .env (ex.: rodando testes
# soltos) — toda instalação de verdade grava sua própria chave em
# launcher.py::garantir_env(), então isso nunca deveria ser usado em
# produção depois dessa mudança.
SECRET_KEY = os.getenv("SECRET_KEY", "VERTEXERP2026SECRET")

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24


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