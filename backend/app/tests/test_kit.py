def _criar_produto(db, nome, estoque, preco_venda=10.0):
    from app.models.produto import Produto

    produto = Produto(
        codigo=f"KIT-{nome}",
        nome=nome,
        preco_custo=5.0,
        preco_venda=preco_venda,
        estoque=estoque,
        estoque_minimo=0,
        ativo=True,
    )
    db.add(produto)
    db.commit()
    db.refresh(produto)
    return produto


def _criar_kit_com_componentes(client, auth_headers, db):
    componente_a = _criar_produto(db, "Componente A", estoque=20)
    componente_b = _criar_produto(db, "Componente B", estoque=10)

    kit = _criar_produto(db, "Kit Combo", estoque=0)
    client.put(
        f"/produtos/{kit.id}",
        json={
            "codigo": kit.codigo,
            "nome": kit.nome,
            "preco_custo": "5.00",
            "preco_venda": "10.00",
            "estoque": 0,
            "estoque_minimo": 0,
            "ativo": True,
            "eh_kit": True,
        },
        headers=auth_headers,
    )

    client.post(
        f"/produtos/{kit.id}/itens-kit",
        json={"produto_componente_id": componente_a.id, "quantidade": 2},
        headers=auth_headers,
    )
    client.post(
        f"/produtos/{kit.id}/itens-kit",
        json={"produto_componente_id": componente_b.id, "quantidade": 1},
        headers=auth_headers,
    )

    return kit, componente_a, componente_b


def test_adicionar_item_kit_sem_marcar_eh_kit_falha(
    client, auth_headers, produto
):
    outro = produto

    response = client.post(
        f"/produtos/{produto.id}/itens-kit",
        json={"produto_componente_id": outro.id, "quantidade": 1},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_kit_nao_pode_ter_a_si_mesmo_como_componente(
    client, auth_headers, db
):
    kit = _criar_produto(db, "Kit Auto", estoque=0)
    client.put(
        f"/produtos/{kit.id}",
        json={
            "codigo": kit.codigo,
            "nome": kit.nome,
            "preco_custo": "5.00",
            "preco_venda": "10.00",
            "estoque": 0,
            "estoque_minimo": 0,
            "ativo": True,
            "eh_kit": True,
        },
        headers=auth_headers,
    )

    response = client.post(
        f"/produtos/{kit.id}/itens-kit",
        json={"produto_componente_id": kit.id, "quantidade": 1},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_kit_de_kit_falha(client, auth_headers, db):
    kit, _, _ = _criar_kit_com_componentes(client, auth_headers, db)

    outro_kit = _criar_produto(db, "Outro Kit", estoque=0)
    client.put(
        f"/produtos/{outro_kit.id}",
        json={
            "codigo": outro_kit.codigo,
            "nome": outro_kit.nome,
            "preco_custo": "5.00",
            "preco_venda": "10.00",
            "estoque": 0,
            "estoque_minimo": 0,
            "ativo": True,
            "eh_kit": True,
        },
        headers=auth_headers,
    )

    response = client.post(
        f"/produtos/{outro_kit.id}/itens-kit",
        json={"produto_componente_id": kit.id, "quantidade": 1},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_vender_kit_baixa_estoque_dos_componentes(
    client, auth_headers, db, caixa_aberto
):
    kit, componente_a, componente_b = _criar_kit_com_componentes(
        client, auth_headers, db
    )

    response = client.post(
        "/vendas/",
        json={
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": kit.id,
                    "quantidade": 3,
                    "valor_unitario": "10.00",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 201

    kit_depois = client.get(
        f"/produtos/{kit.id}", headers=auth_headers
    ).json()
    a_depois = client.get(
        f"/produtos/{componente_a.id}", headers=auth_headers
    ).json()
    b_depois = client.get(
        f"/produtos/{componente_b.id}", headers=auth_headers
    ).json()

    # kit em si nunca tem estoque proprio debitado
    assert kit_depois["estoque"] == 0
    # 2 por kit * 3 kits vendidos
    assert a_depois["estoque"] == 20 - 6
    # 1 por kit * 3 kits vendidos
    assert b_depois["estoque"] == 10 - 3


def test_vender_kit_com_componente_sem_estoque_falha(
    client, auth_headers, db, caixa_aberto
):
    kit, componente_a, componente_b = _criar_kit_com_componentes(
        client, auth_headers, db
    )

    response = client.post(
        "/vendas/",
        json={
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    # componente_b so' tem 10 -- 1 por kit * 11 estoura
                    "produto_id": kit.id,
                    "quantidade": 11,
                    "valor_unitario": "10.00",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "Estoque insuficiente" in response.json()["detail"]

    a_inalterado = client.get(
        f"/produtos/{componente_a.id}", headers=auth_headers
    ).json()
    assert a_inalterado["estoque"] == 20


def test_cancelar_venda_de_kit_devolve_componentes(
    client, auth_headers, db, caixa_aberto
):
    kit, componente_a, componente_b = _criar_kit_com_componentes(
        client, auth_headers, db
    )

    venda = client.post(
        "/vendas/",
        json={
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": kit.id,
                    "quantidade": 2,
                    "valor_unitario": "10.00",
                }
            ],
        },
        headers=auth_headers,
    ).json()

    response = client.delete(
        f"/vendas/{venda['id']}", headers=auth_headers
    )

    assert response.status_code == 200

    a_depois = client.get(
        f"/produtos/{componente_a.id}", headers=auth_headers
    ).json()
    b_depois = client.get(
        f"/produtos/{componente_b.id}", headers=auth_headers
    ).json()

    assert a_depois["estoque"] == 20
    assert b_depois["estoque"] == 10
