def test_resumo_dashboard(
    client, auth_headers, produto, cliente, caixa_aberto
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

    # conta a pagar pendente
    client.post(
        "/contas-pagar/",
        json={
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
    # Compras/Fornecedores nao tem mais tela nem API propria (feature
    # removida a pedido do usuario) mas o campo continua existindo na
    # resposta do dashboard -- o app mobile ainda le esses dois campos
    # como obrigatorios (ver mobile/lib/models/dashboard_resumo.dart).
    # Sem nenhuma Compra/Fornecedor criado neste teste, ficam zerados.
    assert dados["compras_hoje"] == 0.0
    assert dados["fornecedores"] == 0
    # a venda em dinheiro gera um lançamento automático no caixa aberto
    assert dados["saldo_caixa"] == float(caixa_aberto.saldo_inicial) + 40.0
    # ContaReceber e uma tabela legada que nao alimenta mais esse KPI
    # -- o saldo real em aberto vem do MovimentoFiado (ver
    # total_fiado_devedor / MovimentoFiadoService.saldo_total).
    assert dados["contas_receber"] == 0.0
    assert dados["contas_pagar"] == 60.0
    assert dados["total_fiado_devedor"] == 0.0
    assert dados["clientes"] == 1
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


def test_dashboard_estoque_baixo_usa_quantidade_da_loja_nao_o_agregado(
    client, auth_headers, db
):
    """Produto compartilhado entre lojas (loja_id=None): o agregado
    (Produto.estoque) pode estar OK mesmo com uma das lojas zerada --
    o alerta de estoque baixo de CADA loja precisa olhar pra
    EstoqueLoja daquela loja especifica, nao pro agregado."""
    from app.models.estoque_loja import EstoqueLoja
    from app.models.loja import Loja
    from app.models.produto import Produto

    loja_a = Loja(nome="Loja A")
    loja_b = Loja(nome="Loja B")
    db.add_all([loja_a, loja_b])
    db.commit()

    produto = Produto(
        codigo="P901",
        nome="Produto Compartilhado",
        categoria="Geral",
        unidade="UN",
        preco_custo=1.0,
        preco_venda=2.0,
        estoque=20,  # agregado: bem acima do minimo
        estoque_minimo=5,
        loja_id=None,
    )
    db.add(produto)
    db.commit()

    # so' a Loja A tem estoque de verdade desse produto -- Loja B nunca
    # recebeu (sem linha nenhuma em EstoqueLoja pra ela).
    db.add(EstoqueLoja(produto_id=produto.id, loja_id=loja_a.id, quantidade=20))
    db.commit()

    resposta_a = client.get(
        f"/dashboard/?loja_id={loja_a.id}", headers=auth_headers
    )
    resposta_b = client.get(
        f"/dashboard/?loja_id={loja_b.id}", headers=auth_headers
    )

    assert resposta_a.json()["estoque_baixo"] == 0
    assert resposta_b.json()["estoque_baixo"] == 1


def test_dashboard_estoque_baixo_usa_minimo_da_loja_com_fallback_pro_global(
    client, auth_headers, db
):
    """EstoqueLoja.estoque_minimo (Onda 1 da Fase 2) precisa ser usado
    quando a loja configurou o dela; loja que nunca configurou (sem
    linha em EstoqueLoja) cai pro minimo GLOBAL do produto, nao pra 0
    -- senao "nunca configurou" viraria "nunca alerta"."""
    from app.models.estoque_loja import EstoqueLoja
    from app.models.loja import Loja
    from app.models.produto import Produto

    loja_configurada = Loja(nome="Loja Configurada")
    loja_sem_config = Loja(nome="Loja Sem Config")
    db.add_all([loja_configurada, loja_sem_config])
    db.commit()

    produto = Produto(
        codigo="P902",
        nome="Produto Minimo Por Loja",
        categoria="Geral",
        unidade="UN",
        preco_custo=1.0,
        preco_venda=2.0,
        estoque=10,
        estoque_minimo=5,  # minimo global
        loja_id=None,
    )
    db.add(produto)
    db.commit()

    # Loja Configurada: quantidade 8, minimo proprio configurado em 10
    # -- 8 <= 10, deveria contar como estoque baixo mesmo estando ACIMA
    # do minimo global (5).
    db.add(
        EstoqueLoja(
            produto_id=produto.id,
            loja_id=loja_configurada.id,
            quantidade=8,
            estoque_minimo=10,
        )
    )
    # Loja Sem Config: nunca teve linha em EstoqueLoja -- quantidade
    # cai pra 0 (fallback existente), minimo cai pro global (5) -- 0 <=
    # 5, tambem conta como estoque baixo.
    db.commit()

    resposta_configurada = client.get(
        f"/dashboard/?loja_id={loja_configurada.id}", headers=auth_headers
    )
    resposta_sem_config = client.get(
        f"/dashboard/?loja_id={loja_sem_config.id}", headers=auth_headers
    )

    assert resposta_configurada.json()["estoque_baixo"] == 1
    assert resposta_sem_config.json()["estoque_baixo"] == 1
