import os

from jose import jwt
from datetime import datetime, timedelta

# Cai no literal antigo só se a instalação não tiver gerado uma chave
# própria (ver launcher.py::garantir_env) — sem isso, uma chave igual em
# toda instalação permite forjar token válido pra qualquer usuário, de
# qualquer loja, sem nunca saber a senha.
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