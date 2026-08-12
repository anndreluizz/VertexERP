from services.api import get, post


def listar_categorias():

    response = get("/categorias/")

    if response.status_code != 200:
        return []

    return response.json()


def criar_categoria(nome: str):

    return post(
        "/categorias/",
        {"nome": nome, "descricao": None},
    )
