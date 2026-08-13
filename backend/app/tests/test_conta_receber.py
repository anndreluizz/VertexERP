def _criar_conta(client, auth_headers, cliente):
    response = client.post(
        "/contas-receber/",
        json={
            "cliente_id": cliente.id,
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": 200.0,
            "observacao": "Conta de teste",
        },
        headers=auth_headers,
    )
    return response.json()


def test_criar_conta_receber(client, auth_headers, cliente):
    conta = _criar_conta(client, auth_headers, cliente)

    assert conta["status"] == "PENDENTE"
    assert conta["valor"] == 200.0


def test_criar_conta_receber_com_cliente_inexistente(client, auth_headers):
    response = client.post(
        "/contas-receber/",
        json={
            "cliente_id": 9999,
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": 200.0,
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Cliente não encontrado."


def test_receber_sem_caixa_aberto(client, auth_headers, cliente):
    conta = _criar_conta(client, auth_headers, cliente)

    response = client.post(
        f"/contas-receber/{conta['id']}/receber",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Nenhum caixa aberto."


def test_receber_conta_com_caixa_aberto(
    client, auth_headers, cliente, caixa_aberto
):
    conta = _criar_conta(client, auth_headers, cliente)

    response = client.post(
        f"/contas-receber/{conta['id']}/receber",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "RECEBIDO"

    caixa = client.get("/caixa/aberto", headers=auth_headers).json()

    assert caixa["saldo_final"] == float(caixa_aberto.saldo_inicial) + 200.0

    movimentos = client.get("/movimentos-caixa/", headers=auth_headers).json()

    recebimento = [m for m in movimentos if m["tipo"] == "RECEBIMENTO"]

    assert len(recebimento) == 1
    assert recebimento[0]["valor"] == 200.0


def test_receber_conta_ja_recebida(client, auth_headers, cliente, caixa_aberto):
    conta = _criar_conta(client, auth_headers, cliente)

    client.post(f"/contas-receber/{conta['id']}/receber", headers=auth_headers)

    response = client.post(
        f"/contas-receber/{conta['id']}/receber",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Conta já foi recebida."


def test_cancelar_conta_receber(client, auth_headers, cliente):
    conta = _criar_conta(client, auth_headers, cliente)

    response = client.post(
        f"/contas-receber/{conta['id']}/cancelar",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELADO"


def test_cancelar_conta_ja_recebida(
    client, auth_headers, cliente, caixa_aberto
):
    conta = _criar_conta(client, auth_headers, cliente)

    client.post(f"/contas-receber/{conta['id']}/receber", headers=auth_headers)

    response = client.post(
        f"/contas-receber/{conta['id']}/cancelar",
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Não é possível cancelar uma conta já recebida."
    )
