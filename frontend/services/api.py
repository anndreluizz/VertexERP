import os
import sys

import requests

# Esse mesmo arquivo roda em dois contextos com portas padrao diferentes:
# o frontend de dev puro (python app.py, sys.frozen=False) fala com
# "uvicorn main:app" rodando na 8000 (padrao do proprio uvicorn); ja o
# frontend empacotado (VertexERP-Frontend.exe, sys.frozen=True) fala com
# o backend empacotado, que usa 58734 de proposito pra nunca colidir com
# um backend de dev na mesma maquina (ver backend/backend_entry.py).
# VERTEXERP_PORT sempre pode sobrescrever os dois, pra testes isolados.
_PORTA_PADRAO = "58734" if getattr(sys, "frozen", False) else "8000"
URL = f"http://127.0.0.1:{os.getenv('VERTEXERP_PORT', _PORTA_PADRAO)}"

TOKEN = None


def definir_url(endereco):
    """Aponta pra um backend em outra máquina (modo Terminal) — chamado
    uma vez no início do app.py, a partir do endereço salvo em
    preferencias_service. Sem isso, URL continua o padrão localhost de
    sempre (instalação de um PC só, sem mudança nenhuma de comportamento)."""

    global URL

    endereco = (endereco or "").strip()

    if not endereco:
        return

    if not endereco.startswith("http://") and not endereco.startswith("https://"):
        endereco = f"http://{endereco}"

    resto = endereco.split("://", 1)[1]

    if ":" not in resto:
        endereco = f"{endereco}:{_PORTA_PADRAO}"

    URL = endereco


def login(usuario: str, senha: str):

    global TOKEN

    response = requests.post(
        f"{URL}/auth/login",
        json={
            "email": usuario,
            "senha": senha,
        },
    )

    if response.status_code == 200:

        TOKEN = response.json()["access_token"]

        return True

    return False


def logout():

    global TOKEN

    TOKEN = None


def existe_usuario():

    # timeout curto de proposito -- essa chamada roda no arranque do
    # app (ver app.py), antes de qualquer tela aparecer. Sem timeout,
    # um PC Terminal apontando pra um servidor que nao responde (fora
    # do ar, endereco errado, rede lenta) trava o app inteiro sem
    # feedback nenhum em vez de cair no dialogo de reconfigurar o
    # endereco que ja existe pra esse caso.
    response = requests.get(f"{URL}/users/existe", timeout=5)

    if response.status_code != 200:
        # se o backend nao respondeu direito, assume que ja existe
        # usuario pra nao empurrar quem ja usa o sistema de volta
        # pro cadastro inicial
        return True

    return response.json().get("data", {}).get("existe", True)


def cadastrar_usuario(nome, email, senha):

    return requests.post(
        f"{URL}/users/",
        json={
            "nome": nome,
            "email": email,
            "senha": senha,
        },
    )


def get(endpoint: str):

    if TOKEN is None:
        raise Exception("Usuário não autenticado.")

    return requests.get(
        URL + endpoint,
        headers={
            "Authorization": f"Bearer {TOKEN}"
        },
    )


def post(endpoint: str, dados: dict):

    if TOKEN is None:
        raise Exception("Usuário não autenticado.")

    return requests.post(
        URL + endpoint,
        json=dados,
        headers={
            "Authorization": f"Bearer {TOKEN}"
        },
    )


def put(endpoint: str, dados: dict):

    if TOKEN is None:
        raise Exception("Usuário não autenticado.")

    return requests.put(
        URL + endpoint,
        json=dados,
        headers={
            "Authorization": f"Bearer {TOKEN}"
        },
    )


def delete(endpoint: str):

    if TOKEN is None:
        raise Exception("Usuário não autenticado.")

    return requests.delete(
        URL + endpoint,
        headers={
            "Authorization": f"Bearer {TOKEN}"
        },
    )


def dashboard():

    response = get("/dashboard")

    if response.status_code == 200:
        return response.json()

    return {}


def me():

    response = get("/auth/me")

    if response.status_code == 200:
        return response.json()

    return {}


def usuario_e_admin():
    """Se o usuário logado é administrador -- usado pra esconder ações
    restritas (cancelar venda, gerenciar fornecedores etc.) de quem
    não tem permissão, além da checagem que o backend já faz."""

    return bool(me().get("admin"))


def configuracoes():

    response = get("/configuracoes")

    if response.status_code == 200:
        return response.json()

    return {}


def atualizar_configuracoes(dados):

    return put("/configuracoes/", dados)


def trocar_senha(senha_atual, senha_nova):

    return put(
        "/auth/senha",
        {
            "senha_atual": senha_atual,
            "senha_nova": senha_nova,
        },
    )