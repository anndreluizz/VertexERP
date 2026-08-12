def test_criar_categoria(client, auth_headers):
    response = client.post(
        "/categorias/",
        json={"nome": "Bebidas", "descricao": "Bebidas em geral"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["nome"] == "Bebidas"
    assert dados["ativo"] is True


def test_criar_categoria_duplicada(client, auth_headers):
    client.post(
        "/categorias/",
        json={"nome": "Bebidas"},
        headers=auth_headers,
    )

    response = client.post(
        "/categorias/",
        json={"nome": "Bebidas"},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Categoria já cadastrada."


def test_listar_categorias(client, auth_headers):
    client.post(
        "/categorias/",
        json={"nome": "Limpeza"},
        headers=auth_headers,
    )

    response = client.get("/categorias/", headers=auth_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_atualizar_categoria(client, auth_headers):
    criada = client.post(
        "/categorias/",
        json={"nome": "Limpeza"},
        headers=auth_headers,
    ).json()

    response = client.put(
        f"/categorias/{criada['id']}",
        json={"descricao": "Produtos de limpeza"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["descricao"] == "Produtos de limpeza"


def test_atualizar_categoria_inexistente(client, auth_headers):
    response = client.put(
        "/categorias/9999",
        json={"descricao": "x"},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Categoria não encontrada."


def test_excluir_categoria(client, auth_headers):
    criada = client.post(
        "/categorias/",
        json={"nome": "Limpeza"},
        headers=auth_headers,
    ).json()

    response = client.delete(
        f"/categorias/{criada['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    listagem = client.get("/categorias/", headers=auth_headers)

    assert listagem.json() == []
