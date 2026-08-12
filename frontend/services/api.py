import os

import requests

URL = "http://127.0.0.1:8000"

TOKEN = None
ADMIN = False


def login(usuario: str, senha: str):

    global TOKEN, ADMIN

    response = requests.post(
        f"{URL}/auth/login",
        json={
            "email": usuario,
            "senha": senha,
        },
    )

    if response.status_code == 200:

        TOKEN = response.json()["access_token"]

        perfil = get("/users/me")

        ADMIN = (
            perfil.status_code == 200
            and perfil.json()["data"]["admin"]
        )

        return True

    return False


def usuario_e_admin():
    return ADMIN


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


def post_file(endpoint: str, campo: str, caminho_arquivo: str):

    if TOKEN is None:
        raise Exception("Usuário não autenticado.")

    with open(caminho_arquivo, "rb") as arquivo:
        return requests.post(
            URL + endpoint,
            files={
                campo: (os.path.basename(caminho_arquivo), arquivo)
            },
            headers={
                "Authorization": f"Bearer {TOKEN}"
            },
        )


def dashboard():

    response = get("/dashboard")

    if response.status_code == 200:
        return response.json()

    raise Exception(
        f"Falha ao carregar o dashboard (HTTP {response.status_code}): "
        f"{response.text}"
    )