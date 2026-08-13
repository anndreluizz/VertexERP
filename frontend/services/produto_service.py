from services.api import get, post, put, delete

# a API nunca devolve mais que isso por chamada (ver produtos.py no
# backend) -- listar_produtos() varre todas as paginas por baixo dos
# panos, entao pra quem chama continua parecendo uma lista so, so que
# agora sem truncar silenciosamente em 100 registros.
_TAMANHO_PAGINA = 500


# ==========================================
# LISTAR PRODUTOS
# ==========================================

def listar_produtos():

    produtos = []
    pagina = 0

    while True:

        response = get(
            f"/produtos?skip={pagina * _TAMANHO_PAGINA}"
            f"&limit={_TAMANHO_PAGINA}"
        )

        if response.status_code != 200:
            break

        lote = response.json()
        produtos.extend(lote)

        if len(lote) < _TAMANHO_PAGINA:
            break

        pagina += 1

    return produtos


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