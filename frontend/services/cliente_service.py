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


def obter_foto_cliente(cliente_id):

    response = get(f"/clientes/{cliente_id}/foto")

    if response.status_code != 200:
        return None

    return response.content


def listar_observacoes_cliente(cliente_id):

    response = get(f"/clientes/{cliente_id}/observacoes")

    if response.status_code != 200:
        return []

    return response.json()


def criar_observacao_cliente(cliente_id, texto):

    return post(f"/clientes/{cliente_id}/observacoes", {"texto": texto})


def excluir_observacao_cliente(cliente_id, observacao_id):

    return delete(f"/clientes/{cliente_id}/observacoes/{observacao_id}")
