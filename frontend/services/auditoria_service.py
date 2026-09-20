from services.api import get


def listar_logs_auditoria(usuario_id=None, acao=None):

    params = []
    if usuario_id is not None:
        params.append(f"usuario_id={usuario_id}")
    if acao:
        params.append(f"acao={acao}")

    endpoint = "/auditoria/"
    if params:
        endpoint += "?" + "&".join(params)

    response = get(endpoint)

    if response.status_code != 200:
        return []

    return response.json()
