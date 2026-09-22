from services.api import get, post


def listar(skip=0, limit=20):

    response = get(f"/notificacoes/?skip={skip}&limit={limit}")

    if response.status_code != 200:
        return []

    return response.json()


def contagem_nao_lidas():

    response = get("/notificacoes/nao-lidas")

    if response.status_code != 200:
        return 0

    return response.json().get("nao_lidas", 0)


def marcar_lida(notificacao_id):
    return post(f"/notificacoes/{notificacao_id}/marcar-lida", {})


def marcar_todas_lidas():
    return post("/notificacoes/marcar-todas-lidas", {})
