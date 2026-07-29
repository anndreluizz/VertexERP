from services.api import get, post, put, delete


def listar_categorias_despesa():

    response = get("/categorias-despesa/")

    if response.status_code != 200:
        return []

    return response.json()


def cadastrar_categoria_despesa(nome):

    return post("/categorias-despesa/", {"nome": nome})


def atualizar_categoria_despesa(categoria_id, nome):

    return put(f"/categorias-despesa/{categoria_id}", {"nome": nome})


def excluir_categoria_despesa(categoria_id):

    return delete(f"/categorias-despesa/{categoria_id}")
