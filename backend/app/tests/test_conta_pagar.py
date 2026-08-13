def _criar_conta(client, auth_headers, fornecedor):
    response = client.post(
        "/contas-pagar/",
        json={
            "fornecedor_id": fornecedor.id,
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": "150.00",
            "observacao": "Conta de teste",
        },
        headers=auth_headers,
    )
    return response.json()


def test_criar_conta_pagar(client, auth_headers, fornecedor):
    conta = _criar_conta(client, auth_headers, fornecedor)

    assert conta["status"] == "PENDENTE"
    assert float(conta["valor"]) == 150.0


def test_pagar_sem_forma_pagamento_nao_exige_caixa(
    client, auth_headers, fornecedor
):
    # Despesa paga via PIX/transferência (ou sem forma informada) não
    # sai da gaveta física do caixa do PDV -- não precisa de um caixa
    # aberto pra ser marcada como paga.
    conta = _criar_conta(client, auth_headers, fornecedor)

    response = client.post(
        f"/contas-pagar/{conta['id']}/pagar",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "PAGO"


def test_pagar_em_dinheiro_sem_caixa_aberto(client, auth_headers, fornecedor):
    conta = _criar_conta(client, auth_headers, fornecedor)

    response = client.post(
        f"/contas-pagar/{conta['id']}/pagar",
        json={"forma_pagamento": "DINHEIRO"},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Nenhum caixa aberto."


def test_pagar_em_dinheiro_com_caixa_aberto_estorna_saldo(
    client, auth_headers, fornecedor, caixa_aberto
):
    conta = _criar_conta(client, auth_headers, fornecedor)

    response = client.post(
        f"/contas-pagar/{conta['id']}/pagar",
        json={"forma_pagamento": "DINHEIRO"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "PAGO"

    caixa = client.get("/caixa/aberto", headers=auth_headers).json()

    assert caixa["saldo_final"] == float(caixa_aberto.saldo_inicial) - 150.0

    movimentos = client.get("/movimentos-caixa/", headers=auth_headers).json()

    pagamento = [m for m in movimentos if m["tipo"] == "PAGAMENTO"]

    assert len(pagamento) == 1
    assert pagamento[0]["valor"] == -150.0


def test_pagar_conta_ja_paga(client, auth_headers, fornecedor, caixa_aberto):
    conta = _criar_conta(client, auth_headers, fornecedor)

    client.post(f"/contas-pagar/{conta['id']}/pagar", headers=auth_headers)

    response = client.post(
        f"/contas-pagar/{conta['id']}/pagar",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Conta já foi paga."


def test_cancelar_conta_pagar(client, auth_headers, fornecedor):
    conta = _criar_conta(client, auth_headers, fornecedor)

    response = client.post(
        f"/contas-pagar/{conta['id']}/cancelar",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELADO"


def test_cancelar_conta_ja_paga(client, auth_headers, fornecedor, caixa_aberto):
    # Admin cancela uma conta já paga direto (sem fluxo de aprovação --
    # esse é reservado pra quem NÃO é admin, ver test_authorization.py).
    conta = _criar_conta(client, auth_headers, fornecedor)

    client.post(f"/contas-pagar/{conta['id']}/pagar", headers=auth_headers)

    response = client.post(
        f"/contas-pagar/{conta['id']}/cancelar",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELADO"


def test_criar_conta_pagar_com_numero_boleto(
    client, auth_headers, fornecedor
):
    response = client.post(
        "/contas-pagar/",
        json={
            "fornecedor_id": fornecedor.id,
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": "150.00",
            "numero_boleto": "34191.79001 01043.510047 91020.150008 1 96380000015000",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    conta = response.json()

    assert conta["numero_boleto"] == (
        "34191.79001 01043.510047 91020.150008 1 96380000015000"
    )


def test_criar_conta_pagar_avulsa_sem_fornecedor(client, auth_headers):
    response = client.post(
        "/contas-pagar/",
        json={
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": "80.00",
            "observacao": "Conta de luz",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    conta = response.json()

    assert conta["fornecedor_id"] is None
    assert conta["numero_boleto"] is None


def test_atualizar_numero_boleto(client, auth_headers, fornecedor):
    conta = _criar_conta(client, auth_headers, fornecedor)

    response = client.put(
        f"/contas-pagar/{conta['id']}",
        json={"numero_boleto": "00190.00009 03403.640007 00000.000018 1 90000000010000"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["numero_boleto"] == (
        "00190.00009 03403.640007 00000.000018 1 90000000010000"
    )
