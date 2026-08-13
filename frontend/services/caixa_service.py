from services.api import get, post


# ==========================================
# CAIXA
# ==========================================

def caixa_aberto():

    response = get("/caixa/aberto")

    if response.status_code != 200:
        return None

    return response.json()


def abrir_caixa(saldo_inicial):

    return post(
        "/caixa/abrir",
        {
            "saldo_inicial": saldo_inicial,
        },
    )


def fechar_caixa(valor_contado=None, observacoes=None):

    return post(
        "/caixa/fechar",
        {
            "valor_contado": valor_contado,
            "observacoes": observacoes,
        },
    )


def resumo_caixa():

    response = get("/caixa/resumo")

    if response.status_code != 200:
        return None

    return response.json()


def historico_caixa():

    response = get("/caixa/historico")

    if response.status_code != 200:
        return []

    return response.json()


# ==========================================
# MOVIMENTAÇÕES
# ==========================================

_TAMANHO_PAGINA = 500


def listar_movimentacoes():
    """Busca TODAS as movimentações de caixa, varrendo as páginas por
    baixo dos panos -- essa lista alimenta cálculos agregados (Visão
    Geral), então não pode truncar silenciosamente no limite padrão
    da API."""

    movimentos = []
    skip = 0

    while True:

        response = get(
            f"/movimentos-caixa/?skip={skip}&limit={_TAMANHO_PAGINA}"
        )

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
        "/movimentos-caixa/",
        {
            "tipo": tipo,
            "valor": valor,
            "descricao": descricao,
        },
    )

    return response