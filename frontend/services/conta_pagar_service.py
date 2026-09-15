from services.api import get, post, put, delete, endpoint_com_loja


def listar_contas_pagar():

    response = get("/contas-pagar/")

    if response.status_code != 200:
        return []

    return response.json()


def cadastrar_conta_pagar(dados):

    return post(endpoint_com_loja("/contas-pagar/"), dados)


def atualizar_conta_pagar(conta_id, dados):

    return put(f"/contas-pagar/{conta_id}", dados)


def excluir_conta_pagar(conta_id):

    return delete(f"/contas-pagar/{conta_id}")


def pagar_conta_pagar(
    conta_id,
    forma_pagamento=None,
    comprovante_base64=None,
    comprovante_nome=None,
    comprovante_tipo=None,
):

    dados = {}

    if forma_pagamento:
        dados["forma_pagamento"] = forma_pagamento

    if comprovante_base64:
        dados["comprovante_base64"] = comprovante_base64
        dados["comprovante_nome"] = comprovante_nome
        dados["comprovante_tipo"] = comprovante_tipo

    return post(f"/contas-pagar/{conta_id}/pagar", dados)


def obter_documento_conta_pagar(conta_id):

    return get(f"/contas-pagar/{conta_id}/documento")


def remover_documento_conta_pagar(conta_id):

    return delete(f"/contas-pagar/{conta_id}/documento")


def obter_comprovante_pagamento_conta_pagar(conta_id):

    return get(f"/contas-pagar/{conta_id}/comprovante-pagamento")
