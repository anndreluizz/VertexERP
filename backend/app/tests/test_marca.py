def test_criar_marca(client, auth_headers):
    response = client.post(
        "/marcas/", json={"nome": "Marca Teste"}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["nome"] == "Marca Teste"


def test_criar_marca_duplicada(client, auth_headers):
    client.post("/marcas/", json={"nome": "Duplicada"}, headers=auth_headers)
    response = client.post(
        "/marcas/", json={"nome": "Duplicada"}, headers=auth_headers
    )

    assert response.status_code == 400


def test_listar_marcas(client, auth_headers):
    client.post("/marcas/", json={"nome": "Listagem"}, headers=auth_headers)

    response = client.get("/marcas/", headers=auth_headers)

    assert response.status_code == 200
    assert any(m["nome"] == "Listagem" for m in response.json())


def test_atualizar_marca(client, auth_headers):
    criada = client.post(
        "/marcas/", json={"nome": "Original"}, headers=auth_headers
    ).json()

    response = client.put(
        f"/marcas/{criada['id']}",
        json={"nome": "Atualizada"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["nome"] == "Atualizada"


def test_excluir_marca_requer_admin(client, auth_headers_comum, auth_headers):
    criada = client.post(
        "/marcas/", json={"nome": "Pra Excluir"}, headers=auth_headers
    ).json()

    response = client.delete(
        f"/marcas/{criada['id']}", headers=auth_headers_comum
    )

    assert response.status_code == 403


def test_excluir_marca(client, auth_headers):
    criada = client.post(
        "/marcas/", json={"nome": "Sera Excluida"}, headers=auth_headers
    ).json()

    response = client.delete(
        f"/marcas/{criada['id']}", headers=auth_headers
    )

    assert response.status_code == 200

    depois = client.get(f"/marcas/{criada['id']}", headers=auth_headers)
    assert depois.status_code == 404
