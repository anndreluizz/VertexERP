from services.api import get, post, put, delete


def listar_perfis():

    response = get("/perfis/")

    if response.status_code != 200:
        return []

    return response.json()


def listar_permissoes_disponiveis():

    response = get("/perfis/permissoes-disponiveis")

    if response.status_code != 200:
        return {}

    return response.json()


def cadastrar_perfil(nome, permissoes):

    return post("/perfis/", {"nome": nome, "permissoes": permissoes})


def atualizar_perfil(perfil_id, nome, permissoes):

    return put(f"/perfis/{perfil_id}", {"nome": nome, "permissoes": permissoes})


def excluir_perfil(perfil_id):

    return delete(f"/perfis/{perfil_id}")
