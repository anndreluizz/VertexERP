from services.api import get, post, endpoint_com_loja


def preview_extrato(ofx_conteudo):

    response = post(
        endpoint_com_loja("/extrato-bancario/preview"),
        {"ofx_conteudo": ofx_conteudo},
    )
    return response


def importar_extrato(ofx_conteudo):

    return post(
        endpoint_com_loja("/extrato-bancario/importar"),
        {"ofx_conteudo": ofx_conteudo},
    )


def listar_transacoes(status=None):

    endpoint = "/extrato-bancario/"
    if status:
        endpoint += f"?status={status}"

    response = get(endpoint_com_loja(endpoint))

    if response.status_code != 200:
        return []

    return response.json()


def sugerir_candidatos(transacao_id):

    response = get(f"/extrato-bancario/{transacao_id}/sugestoes")

    if response.status_code != 200:
        return []

    return response.json()


def conciliar_transacao(transacao_id, conta_pagar_id):

    return post(
        f"/extrato-bancario/{transacao_id}/conciliar",
        {"conta_pagar_id": conta_pagar_id},
    )


def desconciliar_transacao(transacao_id):

    return post(f"/extrato-bancario/{transacao_id}/desconciliar", {})


def ignorar_transacao(transacao_id):

    return post(f"/extrato-bancario/{transacao_id}/ignorar", {})
