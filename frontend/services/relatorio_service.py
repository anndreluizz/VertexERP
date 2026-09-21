from urllib.parse import urlencode

from services.api import get


def relatorio_vendas(data_inicio, data_fim, skip=0, limit=100, **filtros):

    params = {
        "data_fim": data_fim,
        "skip": skip,
        "limit": limit,
    }

    # data_inicio=None significa "sem limite inferior" (opção "Tudo"
    # da tela de Relatórios) -- se mandasse na querystring viraria o
    # literal "None", que o FastAPI não consegue interpretar como date
    if data_inicio is not None:
        params["data_inicio"] = data_inicio

    params.update(
        {chave: valor for chave, valor in filtros.items() if valor not in (None, "")}
    )

    response = get(f"/relatorios/vendas?{urlencode(params)}")

    if response.status_code != 200:
        raise Exception(
            f"Falha ao carregar o relatório de vendas "
            f"(HTTP {response.status_code}): {response.text}"
        )

    return response.json()


def curva_abc(data_inicio, data_fim, loja_id=None, skip=0, limit=100):

    params = {"data_fim": data_fim, "skip": skip, "limit": limit}

    if data_inicio is not None:
        params["data_inicio"] = data_inicio

    if loja_id is not None:
        params["loja_id"] = loja_id

    response = get(f"/relatorios/curva-abc?{urlencode(params)}")

    if response.status_code != 200:
        raise Exception(
            f"Falha ao carregar a curva ABC "
            f"(HTTP {response.status_code}): {response.text}"
        )

    return response.json()


def comparativo_lojas(data_inicio, data_fim):

    params = {"data_fim": data_fim}

    if data_inicio is not None:
        params["data_inicio"] = data_inicio

    response = get(f"/relatorios/comparativo-lojas?{urlencode(params)}")

    if response.status_code != 200:
        raise Exception(
            f"Falha ao carregar o comparativo entre lojas "
            f"(HTTP {response.status_code}): {response.text}"
        )

    return response.json()


def comparativo_estoque():

    response = get("/relatorios/comparativo-estoque")

    if response.status_code != 200:
        raise Exception(
            f"Falha ao carregar o comparativo de estoque "
            f"(HTTP {response.status_code}): {response.text}"
        )

    return response.json()


def sugestao_reposicao(loja_id=None, skip=0, limit=100):

    params = {"skip": skip, "limit": limit}

    if loja_id is not None:
        params["loja_id"] = loja_id

    response = get(f"/relatorios/sugestao-reposicao?{urlencode(params)}")

    if response.status_code != 200:
        raise Exception(
            f"Falha ao carregar a sugestão de reposição "
            f"(HTTP {response.status_code}): {response.text}"
        )

    return response.json()
