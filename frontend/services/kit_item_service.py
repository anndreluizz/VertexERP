from services.api import get, post, delete


def listar_itens_kit(kit_id):

    response = get(f"/produtos/{kit_id}/itens-kit")

    if response.status_code != 200:
        return []

    return response.json()


def adicionar_item_kit(kit_id, produto_componente_id, quantidade):

    return post(
        f"/produtos/{kit_id}/itens-kit",
        {
            "produto_componente_id": produto_componente_id,
            "quantidade": quantidade,
        },
    )


def remover_item_kit(kit_id, item_id):

    return delete(f"/produtos/{kit_id}/itens-kit/{item_id}")
