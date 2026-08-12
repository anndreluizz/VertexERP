def test_ajuste_entrada_aumenta_estoque(client, auth_headers, produto):
    estoque_inicial = produto.estoque

    response = client.post(
        "/estoque/ajuste",
        json={
            "produto_id": produto.id,
            "tipo": "ENTRADA",
            "quantidade": 10,
            "motivo": "Inventário",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["tipo"] == "ENTRADA"

    produto_atualizado = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()

    assert produto_atualizado["estoque"] == estoque_inicial + 10


def test_ajuste_saida_diminui_estoque(client, auth_headers, produto):
    estoque_inicial = produto.estoque

    response = client.post(
        "/estoque/ajuste",
        json={
            "produto_id": produto.id,
            "tipo": "SAIDA",
            "quantidade": 5,
            "motivo": "Quebra",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201

    produto_atualizado = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()

    assert produto_atualizado["estoque"] == estoque_inicial - 5


def test_ajuste_saida_com_estoque_insuficiente(client, auth_headers, produto):
    response = client.post(
        "/estoque/ajuste",
        json={
            "produto_id": produto.id,
            "tipo": "SAIDA",
            "quantidade": produto.estoque + 1,
            "motivo": "Quebra",
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "Estoque insuficiente" in response.json()["detail"]


def test_ajuste_produto_inexistente(client, auth_headers):
    response = client.post(
        "/estoque/ajuste",
        json={
            "produto_id": 9999,
            "tipo": "ENTRADA",
            "quantidade": 1,
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Produto não encontrado."


def test_listar_movimentos_de_estoque(client, auth_headers, produto):
    client.post(
        "/estoque/ajuste",
        json={"produto_id": produto.id, "tipo": "ENTRADA", "quantidade": 10},
        headers=auth_headers,
    )

    response = client.get("/estoque/movimentos", headers=auth_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_listar_movimentos_por_produto(client, auth_headers, produto):
    client.post(
        "/estoque/ajuste",
        json={"produto_id": produto.id, "tipo": "ENTRADA", "quantidade": 10},
        headers=auth_headers,
    )

    response = client.get(
        f"/estoque/movimentos/{produto.id}", headers=auth_headers
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["produto_id"] == produto.id
