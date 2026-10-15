from urllib.parse import urlencode

from services.api import get, put


def resumo(data_inicio, data_fim, loja_id=None):
    """GET /bi/resumo -- indicadores e recomendacoes ja calculados no
    backend (datas em ISO, loja_id None = todas as lojas)."""

    params = {"data_inicio": data_inicio, "data_fim": data_fim}
    if loja_id is not None:
        params["loja_id"] = loja_id

    response = get(f"/bi/resumo?{urlencode(params)}")

    if response.status_code == 403:
        raise Exception(
            "Você não tem permissão para ver a Inteligência de Negócios. "
            "Peça ao administrador a permissão \"Ver Inteligência de Negócios\"."
        )
    if response.status_code != 200:
        raise Exception(
            f"Falha ao carregar a Inteligência de Negócios "
            f"(HTTP {response.status_code}): {response.text}"
        )

    return response.json()


def informar_dinheiro_guardado(valor):
    """PUT /bi/dinheiro-guardado -- total no cofre + banco (o sistema nao
    registra pra onde vai o dinheiro quando o caixa fecha)."""

    response = put("/bi/dinheiro-guardado", {"valor": f"{valor:.2f}"})

    if response.status_code != 200:
        raise Exception(
            f"Não foi possível salvar o dinheiro guardado "
            f"(HTTP {response.status_code}): {response.text}"
        )

    return response.json()
