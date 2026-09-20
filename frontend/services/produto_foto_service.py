from services.api import get, post, put, delete


def listar_fotos_produto(produto_id):

    response = get(f"/produtos/{produto_id}/fotos")

    if response.status_code != 200:
        return []

    return response.json()


def obter_imagem_foto(produto_id, foto_id):

    response = get(f"/produtos/{produto_id}/fotos/{foto_id}/imagem")

    if response.status_code != 200:
        return None

    return response.content


def adicionar_foto_produto(produto_id, imagem_base64, principal=False):

    return post(
        f"/produtos/{produto_id}/fotos",
        {"imagem_base64": imagem_base64, "principal": principal},
    )


def remover_foto_produto(produto_id, foto_id):

    return delete(f"/produtos/{produto_id}/fotos/{foto_id}")


def marcar_foto_principal(produto_id, foto_id):

    return put(f"/produtos/{produto_id}/fotos/{foto_id}/principal", {})
