from services.api import get, post


def saldo_cliente(cliente_id):

    response = get(f"/fiado/saldo/{cliente_id}")

    if response.status_code != 200:
        return 0.0

    return float(response.json().get("saldo", 0) or 0)


def listar_movimentos_cliente(cliente_id):

    response = get(f"/fiado/movimentos/cliente/{cliente_id}")

    if response.status_code != 200:
        return []

    return response.json()


def listar_movimentos():

    response = get("/fiado/movimentos")

    if response.status_code != 200:
        return []

    return response.json()


def registrar_pagamento(
    cliente_id,
    valor,
    forma_pagamento,
    descricao=None,
    data=None,
):

    return post(
        "/fiado/movimentos",
        {
            "cliente_id": cliente_id,
            "tipo": "PAGAMENTO",
            "valor": valor,
            "forma_pagamento": forma_pagamento,
            "descricao": descricao,
            "data": data,
        },
    )


def lancar_fiado_manual(cliente_id, valor, descricao, data=None):

    return post(
        "/fiado/movimentos",
        {
            "cliente_id": cliente_id,
            "tipo": "COMPRA",
            "valor": valor,
            "descricao": descricao,
            "data": data,
        },
    )
