def test_criar_cliente(client, auth_headers):
    response = client.post(
        "/clientes/",
        json={
            "nome": "João da Silva",
            "cpf_cnpj": "11122233344",
            "email": "joao@teste.com",
            "telefone": "11988887777",
            "endereco": "Rua das Flores, 123",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["nome"] == "João da Silva"
    assert dados["endereco"] == "Rua das Flores, 123"
    assert dados["ativo"] is True


def test_criar_cliente_com_cpf_duplicado(client, auth_headers):
    payload = {
        "nome": "João da Silva",
        "cpf_cnpj": "11122233344",
        "email": "joao@teste.com",
        "telefone": "11988887777",
    }

    client.post("/clientes/", json=payload, headers=auth_headers)

    response = client.post("/clientes/", json=payload, headers=auth_headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "CPF/CNPJ já cadastrado."


def test_listar_clientes(client, auth_headers, cliente):
    response = client.get("/clientes/", headers=auth_headers)

    assert response.status_code == 200

    nomes = [c["nome"] for c in response.json()]

    assert cliente.nome in nomes


def test_buscar_cliente_por_id(client, auth_headers, cliente):
    response = client.get(f"/clientes/{cliente.id}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["nome"] == cliente.nome


def test_buscar_cliente_inexistente(client, auth_headers):
    response = client.get("/clientes/9999", headers=auth_headers)

    assert response.status_code == 400


def test_atualizar_cliente(client, auth_headers, cliente):
    response = client.put(
        f"/clientes/{cliente.id}",
        json={
            "nome": "Nome Atualizado",
            "cpf_cnpj": cliente.cpf_cnpj,
            "email": cliente.email,
            "telefone": cliente.telefone,
            "ativo": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["nome"] == "Nome Atualizado"


def test_excluir_cliente_e_soft_delete(client, auth_headers, cliente):
    response = client.delete(f"/clientes/{cliente.id}", headers=auth_headers)

    assert response.status_code == 200

    # soft-delete: o registro continua existindo, só fica inativo
    ainda_existe = client.get(f"/clientes/{cliente.id}", headers=auth_headers)

    assert ainda_existe.status_code == 200
    assert ainda_existe.json()["ativo"] is False
