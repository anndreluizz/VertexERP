from services.api import get, post, put, endpoint_com_loja


def contagem_aberta():

    response = get(endpoint_com_loja("/estoque/contagens/aberta"))

    if response.status_code != 200:
        return None

    return response.json()


def abrir_contagem(observacao=None):

    return post(
        endpoint_com_loja("/estoque/contagens"), {"observacao": observacao}
    )


def registrar_item_contagem(contagem_id, item_id, quantidade_contada):

    return put(
        f"/estoque/contagens/{contagem_id}/itens/{item_id}",
        {"quantidade_contada": quantidade_contada},
    )


def finalizar_contagem(contagem_id):

    return post(f"/estoque/contagens/{contagem_id}/finalizar", {})


def cancelar_contagem(contagem_id):

    return post(f"/estoque/contagens/{contagem_id}/cancelar", {})


def listar_contagens():

    response = get("/estoque/contagens")

    if response.status_code != 200:
        return []

    return response.json()
