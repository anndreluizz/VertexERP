def test_resumo_dashboard(
    client, auth_headers, produto, cliente, fornecedor, caixa_aberto
):
    # venda hoje
    client.post(
        "/vendas/",
        json={
            "forma_pagamento": "DINHEIRO",
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

    # compra hoje
    client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": 5,
                    "valor_unitario": "8.00",
                }
            ],
        },
        headers=auth_headers,
    )

    # conta a receber pendente
    client.post(
        "/contas-receber/",
        json={
            "cliente_id": cliente.id,
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": 100.0,
        },
        headers=auth_headers,
    )

    # conta a pagar pendente
    client.post(
        "/contas-pagar/",
        json={
            "fornecedor_id": fornecedor.id,
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": "60.00",
        },
        headers=auth_headers,
    )

    # produto com estoque abaixo do mínimo
    client.post(
        "/produtos/",
        json={
            "codigo": "P900",
            "nome": "Produto com Estoque Baixo",
            "preco_custo": "1.00",
            "preco_venda": "2.00",
            "estoque": 1,
            "estoque_minimo": 10,
        },
        headers=auth_headers,
    )

    response = client.get("/dashboard/", headers=auth_headers)

    assert response.status_code == 200

    dados = response.json()

    assert dados["vendas_hoje"] == 40.0
    assert dados["compras_hoje"] == 40.0
    # a venda em dinheiro gera um lançamento automático no caixa aberto
    assert dados["saldo_caixa"] == float(caixa_aberto.saldo_inicial) + 40.0
    # ContaReceber e uma tabela legada que nao alimenta mais esse KPI
    # -- o saldo real em aberto vem do MovimentoFiado (ver
    # total_fiado_devedor / MovimentoFiadoService.saldo_total).
    assert dados["contas_receber"] == 0.0
    assert dados["contas_pagar"] == 60.0
    assert dados["total_fiado_devedor"] == 0.0
    assert dados["clientes"] == 1
    assert dados["fornecedores"] == 1
    assert dados["produtos"] == 2
    assert dados["estoque_baixo"] == 1
    assert dados["vendas_ontem"] == 0.0

    historico = dados["vendas_ultimos_7_dias"]
    assert len(historico) == 7
    assert historico[-1]["total"] == 40.0


def test_dashboard_vendas_ontem_e_historico_7_dias(client, auth_headers, db):
    from datetime import datetime, timedelta

    from app.models.venda import Venda

    ontem = datetime.utcnow() - timedelta(days=1)

    venda_ontem = Venda(
        cliente_id=None,
        valor_total=99.0,
        desconto=0,
        forma_pagamento="DINHEIRO",
        status="FINALIZADA",
        data=ontem,
    )
    db.add(venda_ontem)
    db.commit()

    response = client.get("/dashboard/", headers=auth_headers)

    assert response.status_code == 200

    dados = response.json()

    assert dados["vendas_ontem"] == 99.0

    historico = dados["vendas_ultimos_7_dias"]

    assert len(historico) == 7
    assert historico[-1]["data"] == datetime.utcnow().date().isoformat()
    assert historico[-2]["data"] == ontem.date().isoformat()
    assert historico[-2]["total"] == 99.0


def test_dashboard_total_fiado_devedor(client, auth_headers, cliente):
    outro = client.post(
        "/clientes/",
        json={"nome": "Outro Cliente", "cpf_cnpj": "99988877766"},
        headers=auth_headers,
    ).json()

    # cliente 1: deve R$ 100
    client.post(
        "/fiado/compra",
        json={"cliente_id": cliente.id, "valor": 100.0},
        headers=auth_headers,
    )

    # cliente 2: comprou R$ 50 e já quitou tudo (saldo zerado -- não
    # pode pagar mais do que deve, ver MovimentoFiadoService.criar).
    # O total do dashboard deve refletir só a dívida do cliente 1.
    client.post(
        "/fiado/compra",
        json={"cliente_id": outro["id"], "valor": 50.0},
        headers=auth_headers,
    )
    client.post(
        "/fiado/pagamento",
        json={"cliente_id": outro["id"], "valor": 50.0},
        headers=auth_headers,
    )

    response = client.get("/dashboard/", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["total_fiado_devedor"] == 100.0
