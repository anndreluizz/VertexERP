from services.api import get, put, post_file


def buscar_configuracoes():

    response = get("/configuracoes/")

    if response.status_code != 200:
        return {}

    return response.json()


def atualizar_configuracoes(dados):

    return put("/configuracoes/", dados)


def enviar_logo(caminho_arquivo):

    return post_file("/configuracoes/logo", "arquivo", caminho_arquivo)


def buscar_logo_bytes():

    response = get("/configuracoes/logo")

    if response.status_code != 200:
        return None

    return response.content
