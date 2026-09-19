def test_criar_compra_da_entrada_de_estoque(client, auth_headers, fornecedor, produto):
    estoque_inicial = produto.estoque

    response = client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {"produto_id": produto.id, "quantidade": 5, "valor_unitario": "8.00"}
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    dados = response.json()
    assert dados["fornecedor_id"] == fornecedor.id
    assert dados["status"] == "FINALIZADA"
    assert float(dados["valor_total"]) == 40.0

    produto_atualizado = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()
    assert produto_atualizado["estoque"] == estoque_inicial + 5


def test_criar_compra_gera_movimento_estoque(client, auth_headers, fornecedor, produto):
    client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {"produto_id": produto.id, "quantidade": 3, "valor_unitario": "5.00"}
            ],
        },
        headers=auth_headers,
    )

    movimentos = client.get(
        f"/estoque/movimentos/produto/{produto.id}", headers=auth_headers
    ).json()

    assert any(
        m["tipo"] == "ENTRADA" and m["quantidade"] == 3 for m in movimentos
    )


def test_criar_compra_produto_inexistente(client, auth_headers, fornecedor):
    response = client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {"produto_id": 999999, "quantidade": 1, "valor_unitario": "1.00"}
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_listar_compras(client, auth_headers, fornecedor, produto):
    client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {"produto_id": produto.id, "quantidade": 1, "valor_unitario": "1.00"}
            ],
        },
        headers=auth_headers,
    )

    response = client.get("/compras/", headers=auth_headers)

    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_cancelar_compra_reverte_estoque(client, auth_headers, fornecedor, produto):
    estoque_inicial = produto.estoque

    criada = client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {"produto_id": produto.id, "quantidade": 4, "valor_unitario": "2.00"}
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

    cancelada = client.get(
        f"/compras/{criada['id']}", headers=auth_headers
    ).json()
    assert cancelada["status"] == "CANCELADA"
    assert cancelada["cancelado_em"] is not None


def test_cancelar_compra_duas_vezes_falha(client, auth_headers, fornecedor, produto):
    criada = client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {"produto_id": produto.id, "quantidade": 1, "valor_unitario": "1.00"}
            ],
        },
        headers=auth_headers,
    ).json()

    client.delete(f"/compras/{criada['id']}", headers=auth_headers)
    segunda = client.delete(f"/compras/{criada['id']}", headers=auth_headers)

    assert segunda.status_code == 400


def test_cancelar_compra_requer_admin(client, auth_headers_comum, fornecedor, produto):
    response = client.delete(
        f"/compras/999999", headers=auth_headers_comum
    )

    assert response.status_code == 403
