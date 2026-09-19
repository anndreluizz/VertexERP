from services.api import get, post, put, delete, endpoint_com_loja

_TAMANHO_PAGINA = 500


def listar_fornecedores():

    fornecedores = []
    pagina = 0

    while True:

        response = get(
            f"/fornecedores?skip={pagina * _TAMANHO_PAGINA}"
            f"&limit={_TAMANHO_PAGINA}"
        )

        if response.status_code != 200:
            if pagina == 0:
                raise Exception(
                    "Não foi possível carregar os fornecedores "
                    f"(servidor respondeu {response.status_code})."
                )
            break

        lote = response.json()
        fornecedores.extend(lote)

        if len(lote) < _TAMANHO_PAGINA:
            break

        pagina += 1

    return fornecedores


def buscar_fornecedor(fornecedor_id):
    response = get(f"/fornecedores/{fornecedor_id}")

    if response.status_code != 200:
        return None

    return response.json()


def cadastrar_fornecedor(dados):
    return post("/fornecedores", dados)


def atualizar_fornecedor(fornecedor_id, dados):
    return put(f"/fornecedores/{fornecedor_id}", dados)


def excluir_fornecedor(fornecedor_id):
    return delete(f"/fornecedores/{fornecedor_id}")


def importar_nfe_preview(xml_conteudo):
    return post(
        endpoint_com_loja("/fornecedores/importar-nfe"),
        {"xml_conteudo": xml_conteudo},
    )
