from services.api import post


def finalizar_venda(
    itens,
    forma_pagamento,
    cliente_id=None,
    desconto=0,
    observacao=None,
    data_vencimento=None,
):

    dados = {
        "cliente_id": cliente_id,
        "observacao": observacao,
        "desconto": desconto,
        "forma_pagamento": forma_pagamento,
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