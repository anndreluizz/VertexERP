from services.api import get, post, put, delete, endpoint_com_loja


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


def lancar_fiado_manual(cliente_id, valor, descricao, data=None, registrar_venda=False):
    """registrar_venda=True ("Compra fiada" na ficha): o backend também
    cria uma venda a prazo, que conta na tela de Vendas, no total da
    vendedora e no faturamento. False ("Dívida anterior"): só fiado."""

    return post(
        endpoint_com_loja("/fiado/movimentos"),
        {
            "cliente_id": cliente_id,
            "tipo": "COMPRA",
            "valor": valor,
            "descricao": descricao,
            "data": data,
            "registrar_venda": registrar_venda,
        },
    )


def lancar_haver(cliente_id, valor, descricao, data=None):
    """Credito manual em favor do cliente (desconto, devolucao,
    cortesia) -- reduz o saldo devedor igual um pagamento, mas nunca
    mexe no caixa (nao e dinheiro recebido de verdade)."""

    return post(
        "/fiado/movimentos",
        {
            "cliente_id": cliente_id,
            "tipo": "HAVER",
            "valor": valor,
            "descricao": descricao,
            "data": data,
        },
    )


def editar_movimento(movimento_id, valor=None, descricao=None):
    """Corrige um lançamento de fiado errado (valor e/ou descrição).
    Se era um PAGAMENTO que tinha entrado no caixa, o backend já ajusta
    a diferença automaticamente no caixa aberto de quem está editando."""

    return put(
        f"/fiado/movimentos/{movimento_id}",
        {
            "valor": valor,
            "descricao": descricao,
        },
    )


def excluir_movimento(movimento_id):
    """Exclui um lançamento de fiado errado. Se era um PAGAMENTO que
    tinha entrado no caixa, o backend já estorna automaticamente no
    caixa aberto de quem está excluindo."""

    return delete(f"/fiado/movimentos/{movimento_id}")
