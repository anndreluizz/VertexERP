"""Servidor HTTPS de teste, portátil -- usado pelos testes Flutter que
precisam de um backend real pra falar com (fluxo TOFU e 2FA, ver
test/tofu_desktop_paridade_test.dart e test/sessao_2fa_test.dart).

Gera um certificado autoassinado novo TODA VEZ que inicia (não depende
de nenhum arquivo de certificado pré-gerado) -- isso já resolve sozinho
o caso de "servidor reinstalado com certificado diferente" que os
testes de TOFU precisam simular: cada vez que o processo é reiniciado
(kill + start de novo), o certificado muda sozinho.

Requer: fastapi, uvicorn, cryptography (ver requirements.txt nesta
mesma pasta).
"""
import datetime
import ipaddress
import os
import sys
import tempfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

import uvicorn
from fastapi import FastAPI, HTTPException

CODIGO_2FA_CERTO = "654321"
VERIFICACAO_ID = "verif-teste-123"


def _gerar_certificado(pasta):
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    agora = datetime.datetime.utcnow()

    certificado = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora)
        .not_valid_after(agora + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                x509.IPAddress(ipaddress.ip_address("127.0.0.2")),
            ]),
            critical=False,
        )
        .sign(chave, hashes.SHA256())
    )

    caminho_cert = os.path.join(pasta, "cert.pem")
    caminho_chave = os.path.join(pasta, "chave.pem")

    with open(caminho_cert, "wb") as arquivo:
        arquivo.write(certificado.public_bytes(serialization.Encoding.PEM))

    with open(caminho_chave, "wb") as arquivo:
        arquivo.write(
            chave.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )

    return caminho_cert, caminho_chave


app = FastAPI()


@app.get("/")
def raiz():
    return {"ok": True}


@app.post("/auth/login")
def login(dados: dict):
    if dados.get("senha") == "com2fa":
        return {"requer_2fa": True, "verificacao_id": VERIFICACAO_ID}

    return {
        "access_token": "token-direto",
        "refresh_token": "refresh-direto",
        "token_type": "bearer",
    }


@app.post("/auth/verificar-2fa")
def verificar_2fa(dados: dict):
    if (
        dados.get("verificacao_id") == VERIFICACAO_ID
        and dados.get("codigo") == CODIGO_2FA_CERTO
    ):
        return {
            "access_token": "token-apos-2fa",
            "refresh_token": "refresh-apos-2fa",
            "token_type": "bearer",
        }

    raise HTTPException(status_code=401, detail="Código inválido ou expirado.")


@app.get("/auth/me")
def me():
    return {
        "id": 1,
        "nome": "Usuario Teste",
        "email": "teste@vertex.com",
        "ativo": True,
        "admin": True,
    }


@app.get("/configuracoes")
def configuracoes():
    return {"nome_loja": "Loja Teste"}


if __name__ == "__main__":
    porta = int(sys.argv[1])

    with tempfile.TemporaryDirectory() as pasta_temp:
        caminho_cert, caminho_chave = _gerar_certificado(pasta_temp)

        uvicorn.run(
            app,
            host="0.0.0.0",
            port=porta,
            log_level="warning",
            ssl_certfile=caminho_cert,
            ssl_keyfile=caminho_chave,
        )
