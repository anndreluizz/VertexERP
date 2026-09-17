from services.api import get, post, put, delete, endpoint_com_loja

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
            endpoint_com_loja(
                f"/produtos?skip={pagina * _TAMANHO_PAGINA}"
                f"&limit={_TAMANHO_PAGINA}"
            )
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

    response = get(endpoint_com_loja(f"/produtos/{produto_id}"))

    if response.status_code != 200:
        return None

    return response.json()


# ==========================================
# CADASTRAR PRODUTO
# ==========================================

def cadastrar_produto(dados):

    return post(
        endpoint_com_loja("/produtos"),
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
        endpoint_com_loja(f"/produtos/{produto_id}"),
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
# ALTERNAR FAVORITO
# ==========================================

def alternar_favorito_produto(produto_id, codigo, nome, favorito):
    """Atualização parcial de verdade -- manda so codigo/nome (exigidos
    pelo schema) mais o favorito, sem os outros campos. O backend usa
    exclude_unset no PUT (ver ProdutoService.atualizar), entao qualquer
    campo que nao vier no corpo da requisicao fica como estava --
    preco, estoque, categoria etc. nao sao tocados. Usado no Pesquisar
    Produto (F1) pra marcar/desmarcar favorito sem abrir o cadastro
    completo."""

    return atualizar_produto(
        produto_id,
        {
            "codigo": codigo,
            "nome": nome,
            "favorito": favorito,
        },
    )


# ==========================================
# OBTER FOTO DO PRODUTO
# ==========================================

def obter_foto_produto(produto_id):

    response = get(f"/produtos/{produto_id}/foto")

    if response.status_code != 200:
        return None

    return response.content