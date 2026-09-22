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
            # so' a 1a pagina falhando vira erro de verdade -- uma
            # pagina seguinte falhando no meio (bem mais raro) ainda
            # devolve o que ja' foi coletado, melhor que jogar fora.
            # Sem isso, "erro de rede" e "zero produtos cadastrados"
            # pareciam a mesma coisa pra tela (ambos viravam lista
            # vazia), e ela nao tinha como mostrar o estado certo.
            if pagina == 0:
                raise Exception(
                    "Não foi possível carregar os produtos "
                    f"(servidor respondeu {response.status_code})."
                )
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


# ==========================================
# HISTORICO DE PRECOS
# ==========================================

def listar_historico_precos(produto_id):

    response = get(f"/produtos/{produto_id}/historico-precos")

    if response.status_code != 200:
        return []

    return response.json()


# ==========================================
# VARIACOES (COR/TAMANHO)
# ==========================================

def listar_variacoes(produto_id):

    response = get(endpoint_com_loja(f"/produtos/{produto_id}/variacoes"))

    if response.status_code != 200:
        return []

    return response.json()


# ==========================================
# IMPORTACAO EM MASSA (CSV)
# ==========================================

def importar_csv_preview(csv_conteudo):

    response = post(
        endpoint_com_loja("/produtos/importar-csv/preview"),
        {"csv_conteudo": csv_conteudo},
    )

    if response.status_code != 200:
        raise Exception(
            f"Falha ao ler o CSV (HTTP {response.status_code}): {response.text}"
        )

    return response.json()


def importar_csv_confirmar(itens):

    response = post(
        endpoint_com_loja("/produtos/importar-csv/confirmar"),
        {"itens": itens},
    )

    if response.status_code != 200:
        raise Exception(
            f"Falha ao importar os produtos "
            f"(HTTP {response.status_code}): {response.text}"
        )

    return response.json()