def test_criar_venda_diminui_estoque(
    client, auth_headers, produto, caixa_aberto
):
    estoque_inicial = produto.estoque

    response = client.post(
        "/vendas/",
        json={
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": 3,
                    "valor_unitario": "20.00",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 201

    dados = response.json()

    assert dados["status"] == "FINALIZADA"
    assert float(dados["valor_total"]) == 60.0

    produto_atualizado = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()

    assert produto_atualizado["estoque"] == estoque_inicial - 3


def test_criar_venda_com_estoque_insuficiente(
    client, auth_headers, produto, caixa_aberto
):
    response = client.post(
        "/vendas/",
        json={
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": produto.estoque + 1,
                    "valor_unitario": "20.00",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "Estoque insuficiente" in response.json()["detail"]

    produto_inalterado = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()

    assert produto_inalterado["estoque"] == produto.estoque


def test_criar_venda_com_produto_inexistente(
    client, auth_headers, caixa_aberto
):
    response = client.post(
        "/vendas/",
        json={
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": 9999,
                    "quantidade": 1,
                    "valor_unitario": "1.00",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_criar_venda_a_prazo_gera_conta_a_receber(
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

    # Venda a prazo não gera mais ContaReceber (tabela legada) -- vira
    # MovimentoFiado direto no caderninho do cliente.
    movimentos = client.get(
        f"/fiado/movimentos/cliente/{cliente.id}", headers=auth_headers
    ).json()

    movimento_da_venda = [m for m in movimentos if m["venda_id"] == venda_id]

    assert len(movimento_da_venda) == 1
    assert movimento_da_venda[0]["tipo"] == "COMPRA"
    assert movimento_da_venda[0]["valor"] == 40.0


def test_venda_em_dinheiro_sem_caixa_aberto_e_bloqueada(
    client, auth_headers, produto
):
    response = client.post(
        "/vendas/",
        json={
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": 1,
                    "valor_unitario": "20.00",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "não existe caixa aberto" in response.json()["detail"].lower()


def test_venda_em_dinheiro_com_caixa_aberto_gera_movimento(
    client, auth_headers, produto, caixa_aberto
):
    response = client.post(
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

    assert response.status_code == 201

    venda_id = response.json()["id"]

    movimentos = client.get(
        "/movimentos-caixa/", headers=auth_headers
    ).json()

    movimento_da_venda = [
        m
        for m in movimentos
        if m["tipo"] == "VENDA" and f"Venda #{venda_id}" in m["descricao"]
    ]

    assert len(movimento_da_venda) == 1
    assert movimento_da_venda[0]["valor"] == 40.0
    assert movimento_da_venda[0]["caixa_id"] == caixa_aberto.id

    caixa_atualizado = client.get(
        "/caixa/aberto", headers=auth_headers
    ).json()

    assert (
        caixa_atualizado["saldo_final"]
        == float(caixa_aberto.saldo_inicial) + 40.0
    )


def test_venda_a_prazo_nao_mexe_no_saldo_do_caixa(
    client, auth_headers, produto, cliente, caixa_aberto
):
    # PRAZO ainda exige um caixa aberto (todo MovimentoCaixa fica preso
    # a um caixa, pro fechamento do turno bater certo -- ver comentário
    # em VendaService.criar), mas diferente de DINHEIRO, não soma nada
    # no saldo_final: nenhum dinheiro entrou na gaveta física.
    response = client.post(
        "/vendas/",
        json={
            "cliente_id": cliente.id,
            "forma_pagamento": "PRAZO",
            "data_vencimento": "2026-12-31T00:00:00",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": 1,
                    "valor_unitario": "20.00",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 201

    caixa_atualizado = client.get(
        "/caixa/aberto", headers=auth_headers
    ).json()

    assert caixa_atualizado["saldo_final"] == float(
        caixa_aberto.saldo_inicial
    )


def test_cancelar_venda_devolve_estoque(
    client, auth_headers, produto, caixa_aberto
):
    estoque_inicial = produto.estoque

    criada = client.post(
        "/vendas/",
        json={
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": 3,
                    "valor_unitario": "20.00",
                }
            ],
        },
        headers=auth_headers,
    ).json()

    response = client.delete(
        f"/vendas/{criada['id']}", headers=auth_headers
    )

    assert response.status_code == 200

    produto_atualizado = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()

    assert produto_atualizado["estoque"] == estoque_inicial


def test_cancelar_venda_com_caixa_aberto_estorna_saldo_do_caixa(
    client, auth_headers, produto, caixa_aberto
):
    criada = client.post(
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
    ).json()

    caixa_apos_venda = client.get(
        "/caixa/aberto", headers=auth_headers
    ).json()

    assert (
        caixa_apos_venda["saldo_final"]
        == float(caixa_aberto.saldo_inicial) + 40.0
    )

    response = client.delete(
        f"/vendas/{criada['id']}", headers=auth_headers
    )

    assert response.status_code == 200

    caixa_apos_cancelamento = client.get(
        "/caixa/aberto", headers=auth_headers
    ).json()

    assert (
        caixa_apos_cancelamento["saldo_final"]
        == caixa_aberto.saldo_inicial
    )

    movimentos = client.get(
        "/movimentos-caixa/", headers=auth_headers
    ).json()

    # A venda continua no banco com status=CANCELADA (nunca é apagada
    # de verdade -- ver VendaService.excluir); a descrição é o que
    # identifica de qual venda veio o estorno.
    estorno_da_venda = [
        m
        for m in movimentos
        if m["tipo"] == "ESTORNO"
        and f"venda #{criada['id']}" in m["descricao"]
    ]

    assert len(estorno_da_venda) == 1
    assert estorno_da_venda[0]["valor"] == -40.0


def test_cancelar_venda_com_caixa_fechado_e_bloqueada(
    client, auth_headers, produto, caixa_aberto
):
    criada = client.post(
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
    ).json()

    estoque_apos_venda = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()["estoque"]

    fechar_response = client.post(
        "/caixa/fechar", json={}, headers=auth_headers
    )
    assert fechar_response.status_code == 200

    response = client.delete(
        f"/vendas/{criada['id']}", headers=auth_headers
    )

    assert response.status_code == 400
    assert "já está fechado" in response.json()["detail"]

    # Cancelamento bloqueado: nem estoque nem a venda devem ser alterados.
    venda_ainda_existe = client.get(
        f"/vendas/{criada['id']}", headers=auth_headers
    )
    assert venda_ainda_existe.status_code == 200

    produto_inalterado = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()
    assert produto_inalterado["estoque"] == estoque_apos_venda
