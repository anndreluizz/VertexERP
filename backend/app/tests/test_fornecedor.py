def test_criar_fornecedor(client, auth_headers):
    response = client.post(
        "/fornecedores/",
        json={
            "razao_social": "Distribuidora ABC LTDA",
            "nome_fantasia": "ABC",
            "cnpj": "11222333000144",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["razao_social"] == "Distribuidora ABC LTDA"
    assert dados["ativo"] is True


def test_criar_fornecedor_com_cnpj_duplicado(client, auth_headers):
    payload = {
        "razao_social": "Distribuidora ABC LTDA",
        "cnpj": "11222333000144",
    }

    client.post("/fornecedores/", json=payload, headers=auth_headers)

    response = client.post("/fornecedores/", json=payload, headers=auth_headers)

    assert response.status_code == 409


def test_listar_fornecedores(client, auth_headers, fornecedor):
    response = client.get("/fornecedores/", headers=auth_headers)

    assert response.status_code == 200

    razoes = [f["razao_social"] for f in response.json()]

    assert fornecedor.razao_social in razoes


def test_buscar_fornecedor_inexistente(client, auth_headers):
    response = client.get("/fornecedores/9999", headers=auth_headers)

    assert response.status_code == 404


def test_atualizar_fornecedor(client, auth_headers, fornecedor):
    response = client.put(
        f"/fornecedores/{fornecedor.id}",
        json={
            "razao_social": "Novo Nome LTDA",
            "cnpj": fornecedor.cnpj,
            "ativo": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["razao_social"] == "Novo Nome LTDA"


def test_excluir_fornecedor(client, auth_headers, fornecedor):
    response = client.delete(
        f"/fornecedores/{fornecedor.id}", headers=auth_headers
    )

    assert response.status_code == 200

    depois = client.get(f"/fornecedores/{fornecedor.id}", headers=auth_headers)

    assert depois.status_code == 404
