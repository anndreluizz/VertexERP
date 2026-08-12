from services.api import get, post, put


# ==========================================
# LISTAR
# ==========================================

def listar_contas_pagar():

    response = get("/contas-pagar?limit=500")

    if response.status_code != 200:
        return []

    return response.json()


# ==========================================
# CADASTRAR
# ==========================================

def cadastrar_conta_pagar(dados):

    return post(
        "/contas-pagar/",
        dados,
    )


# ==========================================
# ATUALIZAR
# ==========================================

def atualizar_conta_pagar(conta_id, dados):

    return put(
        f"/contas-pagar/{conta_id}",
        dados,
    )


# ==========================================
# PAGAR
# ==========================================

def pagar_conta_pagar(conta_id):

    return post(
        f"/contas-pagar/{conta_id}/pagar",
        {},
    )


# ==========================================
# CANCELAR
# ==========================================

def cancelar_conta_pagar(conta_id):

    return post(
        f"/contas-pagar/{conta_id}/cancelar",
        {},
    )
