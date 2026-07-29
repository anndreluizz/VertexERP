from services.api import get, post, put, delete


# ==========================================
# LISTAR PRODUTOS
# ==========================================

def listar_produtos():

    response = get("/produtos")

    if response.status_code != 200:
        return []

    return response.json()


# ==========================================
# BUSCAR PRODUTO
# ==========================================

def buscar_produto(produto_id):

    response = get(f"/produtos/{produto_id}")

    if response.status_code != 200:
        return None

    return response.json()


# ==========================================
# CADASTRAR PRODUTO
# ==========================================

def cadastrar_produto(dados):

    return post(
        "/produtos",
        dados,
    )


# ==========================================
# ATUALIZAR PRODUTO
# ==========================================

def atualizar_produto(
    produto_id,
    dados,
):

    return put(
        f"/produtos/{produto_id}",
        dados,
    )


# ==========================================
# EXCLUIR PRODUTO
# ==========================================

def excluir_produto(produto_id):

    return delete(
        f"/produtos/{produto_id}"
    )


# ==========================================
# OBTER FOTO DO PRODUTO
# ==========================================

def obter_foto_produto(produto_id):

    response = get(f"/produtos/{produto_id}/foto")

    if response.status_code != 200:
        return None

    return response.content