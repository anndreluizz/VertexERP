def test_venda_a_prazo_gera_movimento_de_compra_fiado(
    client, auth_headers, produto, cliente, caixa_aberto
):
    response = client.post(
        "/vendas/",
        json={
            "cliente_id": cliente.id,
            "forma_pagamento": "PRAZO",
            "data_vencimento": "2026-12-31T00:00:00",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": 2,
                    "valor_unitario": "20.00",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 201

    venda_id = response.json()["id"]

    ficha = client.get(
        f"/fiado/cliente/{cliente.id}", headers=auth_headers
    ).json()

    assert ficha["saldo_devedor"] == 40.0
    assert len(ficha["movimentos"]) == 1

    movimento = ficha["movimentos"][0]

    assert movimento["tipo"] == "COMPRA"
    assert movimento["valor"] == 40.0
    assert movimento["venda_id"] == venda_id
    # a descrição referencia a venda (não lista produtos -- uma venda
    # pode ter vários itens, o detalhe fica em GET /vendas/{id}/itens)
    assert str(venda_id) in movimento["descricao"]


def test_registrar_pagamento_abate_saldo(
    client, auth_headers, produto, cliente, caixa_aberto
):
    client.post(
        "/vendas/",
        json={
            "cliente_id": cliente.id,
            "forma_pagamento": "PRAZO",
            "data_vencimento": "2026-12-31T00:00:00",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": 5,
                    "valor_unitario": "20.00",
                }
            ],
        },
        headers=auth_headers,
    )

    response = client.post(
        "/fiado/pagamento",
        json={
            "cliente_id": cliente.id,
            "valor": 40.0,
            "descricao": "Pagamento parcial",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["tipo"] == "PAGAMENTO"

    ficha = client.get(
        f"/fiado/cliente/{cliente.id}", headers=auth_headers
    ).json()

    assert ficha["saldo_devedor"] == 60.0
    assert len(ficha["movimentos"]) == 2


def test_varias_compras_e_pagamentos_ate_quitar(
    client, auth_headers, produto, cliente, caixa_aberto
):
    for _ in range(2):
        client.post(
            "/vendas/",
            json={
                "cliente_id": cliente.id,
                "forma_pagamento": "PRAZO",
                "data_vencimento": "2026-12-31T00:00:00",
                "itens": [
                    {
                        "produto_id": produto.id,
                        "quantidade": 1,
                        "valor_unitario": "25.00",
                    }
                ],
            },
            headers=auth_headers,
        )

    # saldo agora é 50.00 — paga tudo em duas parcelas
    client.post(
        "/fiado/pagamento",
        json={"cliente_id": cliente.id, "valor": 30.0},
        headers=auth_headers,
    )
    client.post(
        "/fiado/pagamento",
        json={"cliente_id": cliente.id, "valor": 20.0},
        headers=auth_headers,
    )

    ficha = client.get(
        f"/fiado/cliente/{cliente.id}", headers=auth_headers
    ).json()

    assert ficha["saldo_devedor"] == 0.0
    assert len(ficha["movimentos"]) == 4


def test_pagamento_com_valor_zero_ou_negativo(
    client, auth_headers, cliente
):
    response = client.post(
        "/fiado/pagamento",
        json={"cliente_id": cliente.id, "valor": 0},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Informe um valor de pagamento maior que zero."
    )


def test_pagamento_para_cliente_inexistente(client, auth_headers):
    response = client.post(
        "/fiado/pagamento",
        json={"cliente_id": 9999, "valor": 10.0},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Cliente não encontrado."


def test_ficha_de_cliente_inexistente(client, auth_headers):
    response = client.get("/fiado/cliente/9999", headers=auth_headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "Cliente não encontrado."


def test_ficha_de_cliente_sem_movimentos(client, auth_headers, cliente):
    response = client.get(
        f"/fiado/cliente/{cliente.id}", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["saldo_devedor"] == 0.0
    assert response.json()["movimentos"] == []


def test_saldos_por_cliente_em_lote(client, auth_headers, cliente):
    outro = client.post(
        "/clientes/",
        json={"nome": "Segundo Cliente", "cpf_cnpj": "11122233300"},
        headers=auth_headers,
    ).json()

    client.post(
        "/fiado/compra",
        json={"cliente_id": cliente.id, "valor": 50.0},
        headers=auth_headers,
    )

    client.post(
        "/fiado/compra",
        json={"cliente_id": outro["id"], "valor": 200.0},
        headers=auth_headers,
    )
    client.post(
        "/fiado/pagamento",
        json={"cliente_id": outro["id"], "valor": 30.0},
        headers=auth_headers,
    )

    response = client.get("/fiado/saldos", headers=auth_headers)

    assert response.status_code == 200

    saldos = response.json()

    assert saldos[str(cliente.id)] == 50.0
    assert saldos[str(outro["id"])] == 170.0


def test_saldos_por_cliente_nao_inclui_quem_nunca_teve_movimento(
    client, auth_headers, cliente
):
    response = client.get("/fiado/saldos", headers=auth_headers)

    assert response.status_code == 200
    assert str(cliente.id) not in response.json()


def test_registrar_compra_manual_com_data_historica(
    client, auth_headers, cliente
):
    response = client.post(
        "/fiado/compra",
        json={
            "cliente_id": cliente.id,
            "valor": 35.5,
            "descricao": "Migrado da ficha física",
            "data": "2024-03-10T09:00:00",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201

    dados = response.json()

    assert dados["tipo"] == "COMPRA"
    assert dados["valor"] == 35.5
    assert dados["data"] == "2024-03-10T09:00:00"

    ficha = client.get(
        f"/fiado/cliente/{cliente.id}", headers=auth_headers
    ).json()

    assert ficha["saldo_devedor"] == 35.5


def test_registrar_compra_manual_sem_data_usa_agora(
    client, auth_headers, cliente
):
    response = client.post(
        "/fiado/compra",
        json={"cliente_id": cliente.id, "valor": 10.0},
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["data"] is not None


def test_registrar_compra_manual_com_valor_invalido(
    client, auth_headers, cliente
):
    response = client.post(
        "/fiado/compra",
        json={"cliente_id": cliente.id, "valor": 0},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Informe um valor de compra maior que zero."
    )


def test_registrar_compra_manual_cliente_inexistente(client, auth_headers):
    response = client.post(
        "/fiado/compra",
        json={"cliente_id": 9999, "valor": 10.0},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Cliente não encontrado."


def test_pagamento_com_data_historica(client, auth_headers, cliente):
    client.post(
        "/fiado/compra",
        json={"cliente_id": cliente.id, "valor": 100.0},
        headers=auth_headers,
    )

    response = client.post(
        "/fiado/pagamento",
        json={
            "cliente_id": cliente.id,
            "valor": 40.0,
            "data": "2024-04-01T10:00:00",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["data"] == "2024-04-01T10:00:00"
