from services.api import get, post, endpoint_com_loja


# ==========================================
# CAIXA
# ==========================================

def caixa_aberto():

    response = get(endpoint_com_loja("/caixa/aberto"))

    if response.status_code != 200:
        return None

    return response.json()


def abrir_caixa(saldo_inicial):

    return post(
        endpoint_com_loja("/caixa/abrir"),
        {
            "saldo_inicial": saldo_inicial,
        },
    )


def fechar_caixa(valor_contado=None, observacoes=None, valor_guardado=None,
                 valor_retirado=None):

    return post(
        endpoint_com_loja("/caixa/fechar"),
        {
            "valor_contado": valor_contado,
            "observacoes": observacoes,
            "valor_guardado": valor_guardado,
            "valor_retirado": valor_retirado,
        },
    )


def resumo_caixa():

    response = get(endpoint_com_loja("/caixa/resumo"))

    if response.status_code != 200:
        return None

    return response.json()


def historico_caixa(loja_id=None, limite=20):

    # loja_id aqui e' o filtro escolhido na tela de Relatorios, nao a
    # config fixa do terminal -- por isso nao usa endpoint_com_loja()
    endpoint = f"/caixa/historico?limite={limite}"
    if loja_id is not None:
        endpoint += f"&loja_id={loja_id}"

    response = get(endpoint)

    if response.status_code != 200:
        return []

    return response.json()


def entradas_caixa(inicio=None, fim=None, loja_id=None):
    """Quanto entrou de verdade no periodo, somando todos os caixas
    (vendas menos estornos + fiado recebido, por forma de pagamento)."""

    params = []
    if inicio:
        params.append(f"inicio={inicio.isoformat()}")
    if fim:
        params.append(f"fim={fim.isoformat()}")
    if loja_id is not None:
        params.append(f"loja_id={loja_id}")

    response = get("/caixa/entradas" + ("?" + "&".join(params) if params else ""))

    if response.status_code != 200:
        raise Exception("Não foi possível calcular o dinheiro que entrou.")

    return response.json()


def resumo_caixa_por_id(caixa_id):
    """Resumo de um caixa qualquer, inclusive já fechado."""

    response = get(f"/caixa/{caixa_id}/resumo")

    if response.status_code != 200:
        raise Exception("Não foi possível carregar o resumo do caixa.")

    return response.json()


# ==========================================
# MOVIMENTAÇÕES
# ==========================================

_TAMANHO_PAGINA = 500


def listar_movimentacoes(loja_id=None):
    """Busca TODAS as movimentações de caixa, varrendo as páginas por
    baixo dos panos -- essa lista alimenta cálculos agregados (Visão
    Geral), então não pode truncar silenciosamente no limite padrão
    da API. loja_id=None traz de todas as lojas; quem quer só a do
    terminal (Visão Geral) passa explicitamente."""

    movimentos = []
    skip = 0

    while True:

        endpoint = f"/movimentos-caixa/?skip={skip}&limit={_TAMANHO_PAGINA}"
        if loja_id is not None:
            endpoint += f"&loja_id={loja_id}"

        response = get(endpoint)

        if response.status_code != 200:
            break

        lote = response.json()
        movimentos.extend(lote)

        if len(lote) < _TAMANHO_PAGINA:
            break

        skip += _TAMANHO_PAGINA

    return movimentos


def listar_movimentos_caixa(caixa_id):

    response = get(
        f"/movimentos-caixa/caixa/{caixa_id}"
    )

    if response.status_code != 200:
        return []

    return response.json()


def listar_movimentos_tipo(tipo):

    response = get(
        f"/movimentos-caixa/tipo/{tipo}"
    )

    if response.status_code != 200:
        return []

    return response.json()


def criar_movimento(
    tipo,
    valor,
    descricao=None,
):

    response = post(
        endpoint_com_loja("/movimentos-caixa/"),
        {
            "tipo": tipo,
            "valor": valor,
            "descricao": descricao,
        },
    )

    return response