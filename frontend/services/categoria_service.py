from services.api import get, post, put, delete


def listar_categorias(recentes=False):

    # recentes: a usada por ultimo primeiro (cadastro de produto)
    response = get("/categorias/?recentes=true" if recentes else "/categorias/")

    if response.status_code != 200:
        return []

    return response.json()


def criar_categoria(nome: str):

    return post(
        "/categorias/",
        {"nome": nome, "descricao": None},
    )


def atualizar_categoria(categoria_id, nome):

    return put(f"/categorias/{categoria_id}", {"nome": nome})


def excluir_categoria(categoria_id):

    return delete(f"/categorias/{categoria_id}")
