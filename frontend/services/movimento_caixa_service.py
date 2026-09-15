from services.api import get, post, endpoint_com_loja


# ==========================================
# Criar movimento
# ==========================================

def criar_movimento(
    tipo,
    valor,
    descricao="",
):
    return post(
        endpoint_com_loja("/movimentos-caixa/"),
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