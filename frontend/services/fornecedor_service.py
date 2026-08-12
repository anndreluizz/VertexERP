from services.api import (
    get,
    post,
    put,
    delete,
)


# ==========================================
# LISTAR
# ==========================================

def listar_fornecedores():

    response = get("/fornecedores")

    if response.status_code != 200:
        return []

    return response.json()


# ==========================================
# BUSCAR
# ==========================================

def buscar_fornecedor(fornecedor_id):

    response = get(
        f"/fornecedores/{fornecedor_id}"
    )

    if response.status_code != 200:
        return None

    return response.json()


# ==========================================
# CADASTRAR
# ==========================================

def cadastrar_fornecedor(dados):

    return post(
        "/fornecedores",
        dados,
    )


# ==========================================
# ATUALIZAR
# ==========================================

def atualizar_fornecedor(
    fornecedor_id,
    dados,
):

    return put(
        f"/fornecedores/{fornecedor_id}",
        dados,
    )


# ==========================================
# EXCLUIR
# ==========================================

def excluir_fornecedor(fornecedor_id):

    return delete(
        f"/fornecedores/{fornecedor_id}"
    )