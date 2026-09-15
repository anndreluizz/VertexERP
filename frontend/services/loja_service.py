from services.api import get, post


def listar_lojas():

    # a tela de Configuracoes monta essa aba (e chama isso) assim que
    # o widget e criado -- se ainda nao tiver token (tela construida
    # fora de um login de verdade, como em teste) ou o servidor cair
    # no meio, get() levanta excecao direto (nao um response com
    # status != 200); devolver lista vazia e' melhor que travar a tela
    # inteira de configuracoes por causa de uma aba secundaria
    try:
        response = get("/lojas/")
    except Exception:
        return []

    if response.status_code != 200:
        return []

    return response.json()


def criar_loja(nome):
    return post("/lojas/", {"nome": nome})
