import os
import secrets
import sys

from dotenv import load_dotenv
from jose import jwt
from datetime import datetime, timedelta

# Precisa carregar o .env AQUI: este modulo e' importado (via
# auth/dependencies.py) antes de database/session.py, que era o unico
# load_dotenv() -- sem isso SECRET_KEY nunca vinha do .env e toda
# instalacao caia no mesmo literal publico, permitindo forjar token de
# admin. load_dotenv nao sobrescreve variavel ja definida (testes/CI).
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    # Nunca um literal fixo: sem chave configurada, usa uma aleatoria
    # so' deste processo (tokens deixam de valer ao reiniciar -- basta
    # logar de novo). launcher.py::garantir_env grava uma chave fixa no
    # .env de toda instalacao de verdade.
    SECRET_KEY = secrets.token_hex(32)
    print(
        "AVISO: SECRET_KEY ausente no .env -- usando chave temporaria.",
        file=sys.stderr,
    )

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