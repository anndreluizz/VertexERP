from services.api import get, post, put


def listar_usuarios():

    response = get("/users/")

    if response.status_code != 200:
        return []

    return response.json()["data"]


def cadastrar_usuario(nome, email, senha):

    return post(
        "/users/",
        {
            "nome": nome,
            "email": email,
            "senha": senha,
        },
    )


def definir_admin(user_id, admin):

    return put(f"/users/{user_id}/admin", {"admin": admin})


def definir_ativo(user_id, ativo):

    return put(f"/users/{user_id}/ativo", {"ativo": ativo})
