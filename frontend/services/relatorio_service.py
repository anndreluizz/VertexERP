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
