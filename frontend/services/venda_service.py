from services.api import get, post


def listar_vendas():

    response = get("/vendas/")

    if response.status_code != 200:
        return []

    return response.json()


def finalizar_venda(
    itens,
    forma_pagamento,
    cliente_id=None,
    desconto=0,
    observacao=None,
    data_vencimento=None,
    forma_pagamento_2=None,
    valor_forma_2=None,
):

    dados = {
        "cliente_id": cliente_id,
        "observacao": observacao,
        "desconto": desconto,
        "forma_pagamento": forma_pagamento,
        "forma_pagamento_2": forma_pagamento_2,
        "valor_forma_2": valor_forma_2,
        "data_vencimento": data_vencimento,
        "itens": [],
    }

    for item in itens:

        dados["itens"].append(
            {
                "produto_id": item["id"],
                "quantidade": item["quantidade"],
                "valor_unitario": item["preco"],
            }
        )

    return post("/vendas/", dados)