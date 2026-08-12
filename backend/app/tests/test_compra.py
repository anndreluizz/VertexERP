def test_criar_compra_aumenta_estoque(client, auth_headers, fornecedor, produto):
    estoque_inicial = produto.estoque

    response = client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": 10,
                    "valor_unitario": "8.50",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["status"] == "FINALIZADA"
    assert float(dados["valor_total"]) == 85.0

    produto_atualizado = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()

    assert produto_atualizado["estoque"] == estoque_inicial + 10


def test_criar_compra_a_prazo_gera_conta_a_pagar(
    client, auth_headers, fornecedor, produto
):
    response = client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "PRAZO",
            "data_vencimento": "2026-12-31T00:00:00",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": 5,
                    "valor_unitario": "10.00",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    compra_id = response.json()["id"]

    contas = client.get("/contas-pagar/", headers=auth_headers).json()

    conta_da_compra = [c for c in contas if c["compra_id"] == compra_id]

    assert len(conta_da_compra) == 1
    assert float(conta_da_compra[0]["valor"]) == 50.0
    assert conta_da_compra[0]["status"] == "PENDENTE"


def test_criar_compra_com_produto_inexistente(client, auth_headers, fornecedor):
    response = client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": 9999,
                    "quantidade": 1,
                    "valor_unitario": "1.00",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_excluir_compra_devolve_estoque(
    client, auth_headers, fornecedor, produto
):
    estoque_inicial = produto.estoque

    criada = client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": 10,
                    "valor_unitario": "8.50",
                }
            ],
        },
        headers=auth_headers,
    ).json()

    response = client.delete(
        f"/compras/{criada['id']}", headers=auth_headers
    )

    assert response.status_code == 200

    produto_atualizado = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()

    assert produto_atualizado["estoque"] == estoque_inicial
