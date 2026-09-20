from services.api import get, post, put, delete


def listar_centros_custo():

    response = get("/centros-custo/")

    if response.status_code != 200:
        return []

    return response.json()


def cadastrar_centro_custo(nome):

    return post("/centros-custo/", {"nome": nome})


def atualizar_centro_custo(centro_id, nome):

    return put(f"/centros-custo/{centro_id}", {"nome": nome})


def excluir_centro_custo(centro_id):

    return delete(f"/centros-custo/{centro_id}")
