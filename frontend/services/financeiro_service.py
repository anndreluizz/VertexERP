from services.api import get


def fluxo_caixa(dias=30):

    response = get(f"/financeiro/fluxo-caixa?dias={dias}")

    if response.status_code != 200:
        return None

    return response.json()
