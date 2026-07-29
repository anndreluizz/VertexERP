from services.api import get, post, put, delete


def listar_contas_pagar():

    response = get("/contas-pagar/")

    if response.status_code != 200:
        return []

    return response.json()


def cadastrar_conta_pagar(dados):

    return post("/contas-pagar/", dados)


def atualizar_conta_pagar(conta_id, dados):

    return put(f"/contas-pagar/{conta_id}", dados)


def excluir_conta_pagar(conta_id):

    return delete(f"/contas-pagar/{conta_id}")


def pagar_conta_pagar(conta_id):

    return post(f"/contas-pagar/{conta_id}/pagar", {})


def cancelar_conta_pagar(conta_id):

    return post(f"/contas-pagar/{conta_id}/cancelar", {})
