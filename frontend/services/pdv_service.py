from urllib.parse import quote

from services.api import get


def buscar_produto(codigo: str):

    response = get(
        f"/pdv/produto/{codigo}"
    )

    if response.status_code == 200:
        return response.json()

    return None


def pesquisar_produtos(termo: str):

    response = get(
        f"/pdv/produtos?q={quote(termo)}"
    )

    if response.status_code == 200:
        return response.json()

    return []