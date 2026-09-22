from datetime import datetime, timedelta

from app.models.venda import Venda
from app.models.item_venda import ItemVenda
from app.models.produto import Produto


def _periodo_hoje():
    hoje = datetime.utcnow().date().isoformat()
    return {"data_inicio": hoje, "data_fim": hoje}


def _criar_venda_item(db, produto, valor_unitario, quantidade=1, data=None):
    venda = Venda(
        valor_total=valor_unitario * quantidade,
        desconto=0,
        forma_pagamento="DINHEIRO",
        status="FINALIZADA",
        data=data or datetime.utcnow(),
    )
    db.add(venda)
    db.commit()
    db.refresh(venda)

    item = ItemVenda(
        venda_id=venda.id,
        produto_id=produto.id,
        quantidade=quantidade,
        valor_unitario=valor_unitario,
        subtotal=valor_unitario * quantidade,
    )
    db.add(item)
    db.commit()

    return venda


def test_gasto_compras_mensal_agrupa_por_mes(client, auth_headers, fornecedor, produto):
    client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {"produto_id": produto.id, "quantidade": 2, "valor_unitario": "10.00"}
            ],
        },
        headers=auth_headers,
    )

    response = client.get(
        "/relatorios/gasto-compras-mensal", params=_periodo_hoje(), headers=auth_headers
    )

    assert response.status_code == 200
    itens = response.json()
    assert len(itens) == 1
    assert float(itens[0]["total"]) == 20.0


def test_ranking_fornecedores_ordena_por_total_comprado(
    client, auth_headers, fornecedor, produto, db
):
    from app.models.fornecedor import Fornecedor

    fornecedor_b = Fornecedor(
        razao_social="Fornecedor B Ltda", cnpj="99988877000166", ativo=True,
    )
    db.add(fornecedor_b)
    db.commit()
    db.refresh(fornecedor_b)

    client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {"produto_id": produto.id, "quantidade": 1, "valor_unitario": "100.00"}
            ],
        },
        headers=auth_headers,
    )
    client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor_b.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {"produto_id": produto.id, "quantidade": 1, "valor_unitario": "10.00"}
            ],
        },
        headers=auth_headers,
    )

    response = client.get(
        "/relatorios/ranking-fornecedores", params=_periodo_hoje(), headers=auth_headers
    )

    assert response.status_code == 200
    itens = response.json()
    assert itens[0]["nome"] == "Fornecedor Teste"
    assert float(itens[0]["total"]) == 100.0


def test_prazo_medio_pagamento_fornecedores_calcula_dias_ate_vencimento(
    client, auth_headers, fornecedor, produto
):
    vencimento = datetime.utcnow() + timedelta(days=30)

    client.post(
        "/compras/",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "PRAZO",
            "data_vencimento": vencimento.isoformat(),
            "numero_parcelas": 1,
            "itens": [
                {"produto_id": produto.id, "quantidade": 1, "valor_unitario": "50.00"}
            ],
        },
        headers=auth_headers,
    )

    response = client.get("/relatorios/prazo-fornecedores", headers=auth_headers)

    assert response.status_code == 200
    itens = response.json()
    assert len(itens) == 1
    assert itens[0]["nome"] == "Fornecedor Teste"
    assert 29 <= itens[0]["prazo_medio_dias"] <= 30


def test_categorias_sem_venda_ignora_categoria_vendida_recentemente(
    client, auth_headers, db
):
    recente = Produto(
        codigo="CSV-RECENTE", nome="Vendido Recente", categoria="Vendida",
        unidade="UN", preco_custo=1.0, preco_venda=2.0, estoque=0,
        estoque_minimo=0, ativo=True,
    )
    parada = Produto(
        codigo="CSV-PARADA", nome="Nunca Vendido", categoria="Parada",
        unidade="UN", preco_custo=1.0, preco_venda=2.0, estoque=0,
        estoque_minimo=0, ativo=True,
    )
    db.add_all([recente, parada])
    db.commit()
    db.refresh(recente)
    db.refresh(parada)

    _criar_venda_item(db, recente, valor_unitario=2, quantidade=1)

    response = client.get("/relatorios/categorias-sem-venda", headers=auth_headers)

    assert response.status_code == 200
    categorias = [i["categoria"] for i in response.json()]

    assert "Parada" in categorias
    assert "Vendida" not in categorias
