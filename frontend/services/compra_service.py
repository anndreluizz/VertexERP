from services.api import get, post, delete, endpoint_com_loja

_TAMANHO_PAGINA = 500


def listar_compras():

    compras = []
    pagina = 0

    while True:

        response = get(
            f"/compras?skip={pagina * _TAMANHO_PAGINA}"
            f"&limit={_TAMANHO_PAGINA}"
        )

        if response.status_code != 200:
            if pagina == 0:
                raise Exception(
                    "Não foi possível carregar as compras "
                    f"(servidor respondeu {response.status_code})."
                )
            break

        lote = response.json()
        compras.extend(lote)

        if len(lote) < _TAMANHO_PAGINA:
            break

        pagina += 1

    return compras


def buscar_compra(compra_id):
    response = get(f"/compras/{compra_id}")

    if response.status_code != 200:
        return None

    return response.json()


def cancelar_compra(compra_id):
    return delete(endpoint_com_loja(f"/compras/{compra_id}"))


def importar_nfe_confirmar(dados):
    return post(endpoint_com_loja("/compras/importar-nfe"), dados)
