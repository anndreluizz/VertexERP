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


def fechar_caixa():

    return post(
        "/caixa/fechar",
        {},
    )


# ==========================================
# MOVIMENTAÇÕES
# ==========================================

def listar_movimentacoes():

    response = get("/movimentos-caixa/")

    if response.status_code != 200:
        return []

    return response.json()


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