from services.api import get, post, put


def listar_usuarios():

    response = get("/users/")

    if response.status_code != 200:
        return []

    return response.json().get("data", [])


def atualizar_usuario(user_id, dados):

    return put(f"/users/{user_id}", dados)


def criar_usuario(nome, email, senha):

    return post(
        "/users/",
        {
            "nome": nome,
            "email": email,
            "senha": senha,
        },
    )


def redefinir_senha(user_id, senha_nova):

    return put(
        f"/users/{user_id}/senha",
        {"senha_nova": senha_nova},
    )
