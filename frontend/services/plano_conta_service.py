from services.api import get, post, put, delete


def listar_planos_conta():

    response = get("/planos-conta/")

    if response.status_code != 200:
        return []

    return response.json()


def cadastrar_plano_conta(nome, tipo, conta_pai_id=None, codigo=None):

    return post(
        "/planos-conta/",
        {
            "nome": nome,
            "tipo": tipo,
            "conta_pai_id": conta_pai_id,
            "codigo": codigo,
        },
    )


def atualizar_plano_conta(conta_id, nome, tipo, conta_pai_id=None, codigo=None, ativo=True):

    return put(
        f"/planos-conta/{conta_id}",
        {
            "nome": nome,
            "tipo": tipo,
            "conta_pai_id": conta_pai_id,
            "codigo": codigo,
            "ativo": ativo,
        },
    )


def excluir_plano_conta(conta_id):

    return delete(f"/planos-conta/{conta_id}")
