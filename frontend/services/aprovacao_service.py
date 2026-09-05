from services.api import get, post


def listar_pendentes():
    """Só um admin pode chamar isso (a API bloqueia com 403 pra
    qualquer outro usuário) -- quem chama já deve checar admin antes."""

    response = get("/aprovacoes/pendentes")

    if response.status_code != 200:
        return []

    return response.json()


def aprovar(solicitacao_id):
    return post(f"/aprovacoes/{solicitacao_id}/aprovar", {})


def rejeitar(solicitacao_id):
    return post(f"/aprovacoes/{solicitacao_id}/rejeitar", {})
