from services.api import get, post


# ==========================================
# FICHA DO CLIENTE
# ==========================================

def buscar_ficha(cliente_id):

    response = get(f"/fiado/cliente/{cliente_id}")

    if response.status_code != 200:
        return None

    return response.json()


# ==========================================
# SALDOS DE TODOS OS CLIENTES (EM LOTE)
# ==========================================

def buscar_saldos():

    response = get("/fiado/saldos")

    if response.status_code != 200:
        return {}

    return response.json()


# ==========================================
# REGISTRAR PAGAMENTO
# ==========================================

def registrar_pagamento(cliente_id, valor, descricao=None, data=None):

    return post(
        "/fiado/pagamento",
        {
            "cliente_id": cliente_id,
            "valor": valor,
            "descricao": descricao,
            "data": data,
        },
    )


# ==========================================
# LANÇAR COMPRA MANUAL
# ==========================================

def registrar_compra(cliente_id, valor, descricao=None, data=None):

    return post(
        "/fiado/compra",
        {
            "cliente_id": cliente_id,
            "valor": valor,
            "descricao": descricao,
            "data": data,
        },
    )
