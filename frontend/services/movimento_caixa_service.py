from services.api import get, post


# ==========================================
# Criar movimento
# ==========================================

def criar_movimento(
    tipo,
    valor,
    descricao="",
):
    return post(
        "/movimentos-caixa/",
        {
            "tipo": tipo,
            "valor": valor,
            "descricao": descricao,
        },
    )


# ==========================================
# Sangria
# ==========================================

def criar_sangria(
    valor,
    descricao,
):
    return criar_movimento(
        "SANGRIA",
        valor,
        descricao,
    )


# ==========================================
# Suprimento
# ==========================================

def criar_suprimento(
    valor,
    descricao,
):
    return criar_movimento(
        "SUPRIMENTO",
        valor,
        descricao,
    )


# ==========================================
# Listar movimentos
# ==========================================

def listar_movimentos():

    response = get("/movimentos-caixa/")

    if response.status_code != 200:
        return []

    return response.json()


# ==========================================
# Listar por caixa
# ==========================================

def listar_por_caixa(caixa_id):

    response = get(
        f"/movimentos-caixa/caixa/{caixa_id}"
    )

    if response.status_code != 200:
        return []

    return response.json()


# ==========================================
# Listar por tipo
# ==========================================

def listar_por_tipo(tipo):

    response = get(
        f"/movimentos-caixa/tipo/{tipo}"
    )

    if response.status_code != 200:
        return []

    return response.json()