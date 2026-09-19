from services.api import get, post, endpoint_com_loja


# ==========================================
# LISTAR MOVIMENTOS
# ==========================================

def listar_movimentos():

    response = get("/estoque/movimentos")

    if response.status_code != 200:
        return []

    return response.json()


def listar_movimentos_por_produto(produto_id):

    response = get(f"/estoque/movimentos/produto/{produto_id}")

    if response.status_code != 200:
        return []

    return response.json()


# ==========================================
# REGISTRAR AJUSTE
# ==========================================

def ajustar_estoque(dados):

    return post(endpoint_com_loja("/estoque/movimentos"), dados)


# ==========================================
# TRANSFERENCIA ENTRE LOJAS
# ==========================================

def listar_transferencias():

    response = get("/estoque/transferencias")

    if response.status_code != 200:
        return []

    return response.json()


def transferir_estoque(dados):

    return post(endpoint_com_loja("/estoque/transferencias"), dados)
