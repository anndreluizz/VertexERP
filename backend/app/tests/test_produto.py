def test_criar_produto(client, auth_headers):
    response = client.post(
        "/produtos/",
        json={
            "codigo": "P100",
            "nome": "Arroz 5kg",
            "categoria": "Mercearia",
            "preco_custo": "15.00",
            "preco_venda": "22.90",
            "estoque": 30,
            "estoque_minimo": 5,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["codigo"] == "P100"


def test_listar_produtos(client, auth_headers, produto):
    response = client.get("/produtos/", headers=auth_headers)

    assert response.status_code == 200

    codigos = [p["codigo"] for p in response.json()]

    assert produto.codigo in codigos


def test_buscar_produto_inexistente(client, auth_headers):
    response = client.get("/produtos/9999", headers=auth_headers)

    assert response.status_code == 404


def test_atualizar_produto(client, auth_headers, produto):
    response = client.put(
        f"/produtos/{produto.id}",
        json={
            "codigo": produto.codigo,
            "nome": "Nome Atualizado",
            "categoria": produto.categoria,
            "preco_custo": str(produto.preco_custo),
            "preco_venda": str(produto.preco_venda),
            "estoque": produto.estoque,
            "estoque_minimo": produto.estoque_minimo,
            "ativo": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["nome"] == "Nome Atualizado"


def test_atualizar_produto_inexistente(client, auth_headers):
    response = client.put(
        "/produtos/9999",
        json={
            "codigo": "X",
            "nome": "X",
            "preco_custo": "1.00",
            "preco_venda": "2.00",
            "estoque": 0,
            "estoque_minimo": 0,
            "ativo": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_excluir_produto(client, auth_headers, produto):
    # Exclusão é soft-delete (ativo=False) -- um produto já vendido tem
    # itens_venda apontando pra ele, então apagar de vez quebraria a
    # integridade referencial (ver ProdutoService.excluir). O registro
    # continua existindo e buscável por id, só marcado como inativo.
    response = client.delete(f"/produtos/{produto.id}", headers=auth_headers)

    assert response.status_code == 200

    depois = client.get(f"/produtos/{produto.id}", headers=auth_headers)

    assert depois.status_code == 200
    assert depois.json()["ativo"] is False
