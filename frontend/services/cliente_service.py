from services.api import (
    get,
    post,
    put,
    delete,
)


# ==========================================
# LISTAR
# ==========================================

def listar_clientes():

    response = get("/clientes")

    if response.status_code != 200:
        return []

    return response.json()


# ==========================================
# BUSCAR
# ==========================================

def buscar_cliente(cliente_id):

    response = get(
        f"/clientes/{cliente_id}"
    )

    if response.status_code != 200:
        return None

    return response.json()


# ==========================================
# CADASTRAR
# ==========================================

def cadastrar_cliente(dados):

    return post(
        "/clientes",
        dados,
    )


# ==========================================
# ATUALIZAR
# ==========================================

def atualizar_cliente(
    cliente_id,
    dados,
):

    return put(
        f"/clientes/{cliente_id}",
        dados,
    )


# ==========================================
# EXCLUIR
# ==========================================

def excluir_cliente(cliente_id):

    return delete(
        f"/clientes/{cliente_id}"
    )