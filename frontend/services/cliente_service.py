from services.api import get, post, put, delete


def listar_clientes():

    response = get("/clientes/")

    if response.status_code != 200:
        return []

    return response.json()


def buscar_cliente(cliente_id):

    response = get(f"/clientes/{cliente_id}")

    if response.status_code != 200:
        return None

    return response.json()


def cadastrar_cliente(dados):

    return post("/clientes/", dados)


def atualizar_cliente(cliente_id, dados):

    return put(f"/clientes/{cliente_id}", dados)


def excluir_cliente(cliente_id):

    return delete(f"/clientes/{cliente_id}")
