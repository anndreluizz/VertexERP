import requests

URL = "http://127.0.0.1:8000"

TOKEN = None


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