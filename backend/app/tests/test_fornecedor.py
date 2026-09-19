def test_criar_fornecedor(client, auth_headers):
    response = client.post(
        "/fornecedores/",
        json={
            "razao_social": "Novo Fornecedor Ltda",
            "nome_fantasia": "Novo Fornecedor",
            "cnpj": "98.765.432/0001-10",
            "margem_padrao": "25.00",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    dados = response.json()
    assert dados["cnpj"] == "98765432000110"  # so' digitos, mascara removida
    assert dados["margem_padrao"] == 25.0


def test_criar_fornecedor_cnpj_duplicado(client, auth_headers, fornecedor):
    response = client.post(
        "/fornecedores/",
        json={
            "razao_social": "Outro Nome",
            "cnpj": fornecedor.cnpj,
        },
        headers=auth_headers,
    )

    assert response.status_code == 409


def test_listar_fornecedores(client, auth_headers, fornecedor):
    response = client.get("/fornecedores/", headers=auth_headers)

    assert response.status_code == 200
    assert any(f["id"] == fornecedor.id for f in response.json())


def test_buscar_fornecedor(client, auth_headers, fornecedor):
    response = client.get(
        f"/fornecedores/{fornecedor.id}", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["razao_social"] == fornecedor.razao_social


def test_atualizar_fornecedor(client, auth_headers, fornecedor):
    response = client.put(
        f"/fornecedores/{fornecedor.id}",
        json={
            "razao_social": "Nome Atualizado",
            "cnpj": fornecedor.cnpj,
            "margem_padrao": "30.00",
            "ativo": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["razao_social"] == "Nome Atualizado"
    assert response.json()["margem_padrao"] == 30.0


def test_excluir_fornecedor_e_soft_delete(client, auth_headers, fornecedor, db):
    response = client.delete(
        f"/fornecedores/{fornecedor.id}", headers=auth_headers
    )

    assert response.status_code == 200

    # soft-delete: a linha continua existindo, so' ativo vira False --
    # nunca some do banco (Compra tem FK real pra fornecedor_id).
    depois = client.get(
        f"/fornecedores/{fornecedor.id}", headers=auth_headers
    )
    assert depois.status_code == 200
    assert depois.json()["ativo"] is False

    from app.models.fornecedor import Fornecedor

    ainda_existe = (
        db.query(Fornecedor).filter(Fornecedor.id == fornecedor.id).first()
    )
    assert ainda_existe is not None


def test_excluir_fornecedor_requer_admin(client, auth_headers_comum, fornecedor):
    response = client.delete(
        f"/fornecedores/{fornecedor.id}", headers=auth_headers_comum
    )

    assert response.status_code == 403
