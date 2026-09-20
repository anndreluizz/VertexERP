def test_criar_centro_custo(client, auth_headers):
    response = client.post(
        "/centros-custo/", json={"nome": "Loja Centro"}, headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["nome"] == "Loja Centro"


def test_criar_centro_custo_duplicado_falha(client, auth_headers):
    client.post(
        "/centros-custo/", json={"nome": "Marketing"}, headers=auth_headers
    )
    response = client.post(
        "/centros-custo/", json={"nome": "Marketing"}, headers=auth_headers
    )

    assert response.status_code == 400


def test_listar_centros_custo(client, auth_headers):
    client.post(
        "/centros-custo/", json={"nome": "Administrativo"}, headers=auth_headers
    )

    response = client.get("/centros-custo/", headers=auth_headers)

    assert response.status_code == 200
    nomes = [c["nome"] for c in response.json()]
    assert "Administrativo" in nomes


def test_atualizar_centro_custo(client, auth_headers):
    criado = client.post(
        "/centros-custo/", json={"nome": "Operacional"}, headers=auth_headers
    ).json()

    response = client.put(
        f"/centros-custo/{criado['id']}",
        json={"nome": "Operacional Loja 1"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["nome"] == "Operacional Loja 1"


def test_excluir_centro_custo_requer_admin(client, auth_headers_comum):
    response = client.delete(
        "/centros-custo/999999", headers=auth_headers_comum
    )

    assert response.status_code == 403


def test_excluir_centro_custo(client, auth_headers):
    criado = client.post(
        "/centros-custo/", json={"nome": "Descartável"}, headers=auth_headers
    ).json()

    response = client.delete(
        f"/centros-custo/{criado['id']}", headers=auth_headers
    )

    assert response.status_code == 200


def test_conta_pagar_com_centro_custo(client, auth_headers):
    response = client.post(
        "/contas-pagar/",
        json={
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": "150.00",
            "descricao": "Aluguel",
            "centro_custo": "Loja Centro",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["centro_custo"] == "Loja Centro"
