from datetime import datetime, timedelta

from app.models.conta_receber import ContaReceber


def _criar_conta_receber(db, cliente_id, data_vencimento, valor):
    # ContaReceber nao tem mais rota propria (tabela legada, so
    # FinanceiroService.fluxo_caixa ainda le direto do banco) --
    # cria direto pelo model, sem passar por API.
    conta = ContaReceber(
        cliente_id=cliente_id,
        data_vencimento=data_vencimento,
        valor=valor,
        status="PENDENTE",
    )
    db.add(conta)
    db.commit()
    return conta


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
    client, auth_headers, db, caixa_aberto, cliente, fornecedor
):
    dentro_do_periodo = datetime.utcnow() + timedelta(days=10)
    fora_do_periodo = datetime.utcnow() + timedelta(days=90)

    _criar_conta_receber(db, cliente.id, dentro_do_periodo, 100.0)
    _criar_conta_receber(db, cliente.id, fora_do_periodo, 999.0)

    client.post(
        "/contas-pagar/",
        json={
            "fornecedor_id": fornecedor.id,
            "data_vencimento": dentro_do_periodo.isoformat(),
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
        float(caixa_aberto.saldo_inicial) + 100.0 - 40.0
    )
    assert len(dados["itens"]) == 2
