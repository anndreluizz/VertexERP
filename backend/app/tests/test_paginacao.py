def test_produtos_respeita_limit_e_skip(client, auth_headers):
    for i in range(5):
        client.post(
            "/produtos/",
            json={
                "codigo": f"PAG{i}",
                "nome": f"Produto Paginado {i}",
                "preco_custo": "1.00",
                "preco_venda": "2.00",
                "estoque": 10,
                "estoque_minimo": 1,
            },
            headers=auth_headers,
        )

    primeira_pagina = client.get(
        "/produtos/?skip=0&limit=2", headers=auth_headers
    ).json()

    segunda_pagina = client.get(
        "/produtos/?skip=2&limit=2", headers=auth_headers
    ).json()

    assert len(primeira_pagina) == 2
    assert len(segunda_pagina) == 2

    # páginas diferentes não se sobrepõem
    ids_primeira = {p["id"] for p in primeira_pagina}
    ids_segunda = {p["id"] for p in segunda_pagina}
    assert ids_primeira.isdisjoint(ids_segunda)


def test_produtos_limit_maximo_e_respeitado(client, auth_headers):
    response = client.get(
        "/produtos/?limit=1000", headers=auth_headers
    )

    assert response.status_code == 422


def test_produtos_limit_padrao_sem_parametros(client, auth_headers, produto):
    response = client.get("/produtos/", headers=auth_headers)

    assert response.status_code == 200
    # comportamento padrão (sem skip/limit) continua igual a antes
    assert len(response.json()) == 1


def test_vendas_respeita_paginacao(
    client, auth_headers, produto, caixa_aberto
):
    for _ in range(3):
        client.post(
            "/vendas/",
            json={
                "forma_pagamento": "DINHEIRO",
                "itens": [
                    {
                        "produto_id": produto.id,
                        "quantidade": 1,
                        "valor_unitario": "5.00",
                    }
                ],
            },
            headers=auth_headers,
        )

    pagina = client.get(
        "/vendas/?skip=1&limit=1", headers=auth_headers
    ).json()

    assert len(pagina) == 1


def test_movimentos_caixa_respeita_paginacao(
    client, auth_headers, caixa_aberto
):
    for _ in range(3):
        client.post(
            "/movimentos-caixa/",
            json={"tipo": "SUPRIMENTO", "descricao": "x", "valor": 10.0},
            headers=auth_headers,
        )

    pagina = client.get(
        "/movimentos-caixa/?skip=1&limit=1", headers=auth_headers
    ).json()

    assert len(pagina) == 1


def test_financeiro_nao_e_afetado_por_limite_de_paginacao(
    client, auth_headers, db, caixa_aberto, cliente
):
    # cria mais contas a receber pendentes do que um "limit" pequeno
    # permitiria, pra garantir que o fluxo de caixa soma todas mesmo
    # assim -- ContaReceber nao tem mais rota propria (tabela legada,
    # so FinanceiroService.fluxo_caixa ainda le direto do banco), cria
    # direto pelo model.
    from datetime import datetime

    from app.models.conta_receber import ContaReceber

    for i in range(3):
        db.add(
            ContaReceber(
                cliente_id=cliente.id,
                data_vencimento=datetime(2026, 8, 1),
                valor=10.0,
                status="PENDENTE",
            )
        )
    db.commit()

    response = client.get(
        "/financeiro/fluxo-caixa?dias=60", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["total_a_receber"] == 30.0
