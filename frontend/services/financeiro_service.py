from services.api import get, endpoint_com_loja


def fluxo_caixa(dias=30):

    response = get(endpoint_com_loja(f"/financeiro/fluxo-caixa?dias={dias}"))

    if response.status_code != 200:
        return None

    return response.json()
