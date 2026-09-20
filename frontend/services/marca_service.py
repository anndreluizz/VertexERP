from services.api import get, post, put, delete


def listar_marcas():

    response = get("/marcas/")

    if response.status_code != 200:
        return []

    return response.json()


def criar_marca(nome: str):

    return post(
        "/marcas/",
        {"nome": nome, "descricao": None},
    )


def atualizar_marca(marca_id, nome):

    return put(f"/marcas/{marca_id}", {"nome": nome})


def excluir_marca(marca_id):

    return delete(f"/marcas/{marca_id}")
