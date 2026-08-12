from services.api import (
    get,
    post,
    delete,
)


# ==========================================
# LISTAR
# ==========================================

def listar_compras():

    response = get("/compras")

    if response.status_code != 200:
        return []

    return response.json()


# ==========================================
# BUSCAR
# ==========================================

def buscar_compra(compra_id):

    response = get(
        f"/compras/{compra_id}"
    )

    if response.status_code != 200:
        return None

    return response.json()


# ==========================================
# CADASTRAR
# ==========================================

def cadastrar_compra(dados):

    return post(
        "/compras",
        dados,
    )


# ==========================================
# EXCLUIR
# ==========================================

def excluir_compra(compra_id):

    return delete(
        f"/compras/{compra_id}"
    )