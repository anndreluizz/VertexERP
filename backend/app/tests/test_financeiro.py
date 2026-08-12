from datetime import datetime, timedelta


def test_fluxo_caixa_sem_caixa_aberto(client, auth_headers):
    response = client.get(
        "/financeiro/fluxo-caixa?dias=30", headers=auth_headers
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["saldo_atual"] == 0.0
    assert dados["total_a_receber"] == 0.0
    assert dados["total_a_pagar"] == 0.0
    assert dados["itens"] == []


def test_fluxo_caixa_considera_apenas_o_periodo(
    client, auth_headers, caixa_aberto, cliente, fornecedor
):
    dentro_do_periodo = (datetime.utcnow() + timedelta(days=10)).isoformat()
    fora_do_periodo = (datetime.utcnow() + timedelta(days=90)).isoformat()

    client.post(
        "/contas-receber/",
        json={
            "cliente_id": cliente.id,
            "data_vencimento": dentro_do_periodo,
            "valor": 100.0,
        },
        headers=auth_headers,
    )

    client.post(
        "/contas-receber/",
        json={
            "cliente_id": cliente.id,
            "data_vencimento": fora_do_periodo,
            "valor": 999.0,
        },
        headers=auth_headers,
    )

    client.post(
        "/contas-pagar/",
        json={
            "fornecedor_id": fornecedor.id,
            "data_vencimento": dentro_do_periodo,
            "valor": "40.00",
        },
        headers=auth_headers,
    )

    response = client.get(
        "/financeiro/fluxo-caixa?dias=30", headers=auth_headers
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["saldo_atual"] == caixa_aberto.saldo_inicial
    assert dados["total_a_receber"] == 100.0
    assert dados["total_a_pagar"] == 40.0
    assert dados["saldo_projetado"] == (
        caixa_aberto.saldo_inicial + 100.0 - 40.0
    )
    assert len(dados["itens"]) == 2
