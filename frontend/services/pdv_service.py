from services.api import get


def buscar_produto(codigo: str):

    response = get(
        f"/pdv/produto/{codigo}"
    )

    if response.status_code == 200:
        return response.json()

    return None