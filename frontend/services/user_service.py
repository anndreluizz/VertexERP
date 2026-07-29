from services.api import get, put, cadastrar_usuario


def listar_usuarios():

    response = get("/users/")

    if response.status_code != 200:
        return []

    return response.json().get("data", [])


def atualizar_usuario(user_id, dados):

    return put(f"/users/{user_id}", dados)


def criar_usuario(nome, email, senha):

    return cadastrar_usuario(nome, email, senha)
