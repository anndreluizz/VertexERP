from datetime import datetime, timedelta

from app.models.venda import Venda
from app.models.item_venda import ItemVenda


def _criar_venda(
    db,
    produto,
    quantidade=3,
    cliente_id=None,
    forma_pagamento="DINHEIRO",
    status="FINALIZADA",
    data=None,
    valor_unitario=None,
):
    valor_unitario = (
        valor_unitario
        if valor_unitario is not None
        else produto.preco_venda
    )

    subtotal = valor_unitario * quantidade

    venda = Venda(
        cliente_id=cliente_id,
        valor_total=subtotal,
        desconto=0,
        forma_pagamento=forma_pagamento,
        status=status,
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
        subtotal=subtotal,
    )
    db.add(item)
    db.commit()

    return venda


def _periodo_hoje():
    hoje = datetime.utcnow().date().isoformat()
    return {"data_inicio": hoje, "data_fim": hoje}


def test_relatorio_vendas_kpis_basico(client, auth_headers, db, produto, cliente):
    _criar_venda(db, produto, quantidade=3, cliente_id=cliente.id)

    response = client.get(
        "/relatorios/vendas",
        params=_periodo_hoje(),
        headers=auth_headers,
    )

    assert response.status_code == 200

    dados = response.json()

    # preco_venda=20, preco_custo=10, quantidade=3 -> receita 60, lucro 30
    assert dados["receita_total"]["atual"] == 60.0
    assert dados["lucro"]["atual"] == 30.0
    assert dados["quantidade_vendas"]["atual"] == 1
    assert dados["ticket_medio"]["atual"] == 60.0
    assert dados["clientes_atendidos"]["atual"] == 1
    assert dados["produtos_vendidos"]["atual"] == 3
    assert dados["margem_lucro"]["atual"] == 50.0


def test_relatorio_vendas_comparacao_periodo_anterior(
    client, auth_headers, db, produto
):
    hoje = datetime.utcnow()
    ontem = hoje - timedelta(days=1)

    _criar_venda(db, produto, quantidade=2, data=hoje)
    _criar_venda(db, produto, quantidade=1, data=ontem)

    response = client.get(
        "/relatorios/vendas",
        params=_periodo_hoje(),
        headers=auth_headers,
    )

    dados = response.json()

    assert dados["receita_total"]["atual"] == 40.0
    assert dados["receita_total"]["anterior"] == 20.0
    assert dados["receita_total"]["variacao_pct"] == 100.0


def test_relatorio_vendas_sem_vendas_no_periodo_anterior(
    client, auth_headers, db, produto
):
    _criar_venda(db, produto, quantidade=1, data=datetime.utcnow())

    response = client.get(
        "/relatorios/vendas",
        params=_periodo_hoje(),
        headers=auth_headers,
    )

    dados = response.json()

    assert dados["receita_total"]["anterior"] == 0.0
    assert dados["receita_total"]["variacao_pct"] is None


def test_relatorio_vendas_exclui_canceladas_por_padrao(
    client, auth_headers, db, produto
):
    _criar_venda(db, produto, quantidade=1, status="FINALIZADA")
    _criar_venda(db, produto, quantidade=5, status="CANCELADA")

    response = client.get(
        "/relatorios/vendas",
        params=_periodo_hoje(),
        headers=auth_headers,
    )

    dados = response.json()

    assert dados["quantidade_vendas"]["atual"] == 1
    assert dados["produtos_vendidos"]["atual"] == 1


def test_relatorio_vendas_filtro_produto_restringe_lucro_mas_nao_receita(
    client, auth_headers, db, produto
):
    from app.models.produto import Produto

    outro_produto = Produto(
        codigo="P002",
        nome="Outro Produto",
        categoria="Geral",
        unidade="UN",
        preco_custo=5.0,
        preco_venda=15.0,
        estoque=50,
        estoque_minimo=5,
        ativo=True,
    )
    db.add(outro_produto)
    db.commit()
    db.refresh(outro_produto)

    venda = Venda(
        valor_total=0,
        desconto=0,
        forma_pagamento="DINHEIRO",
        status="FINALIZADA",
        data=datetime.utcnow(),
    )
    db.add(venda)
    db.commit()
    db.refresh(venda)

    item_1 = ItemVenda(
        venda_id=venda.id,
        produto_id=produto.id,
        quantidade=2,
        valor_unitario=produto.preco_venda,
        subtotal=produto.preco_venda * 2,
    )
    item_2 = ItemVenda(
        venda_id=venda.id,
        produto_id=outro_produto.id,
        quantidade=1,
        valor_unitario=outro_produto.preco_venda,
        subtotal=outro_produto.preco_venda,
    )
    venda.valor_total = item_1.subtotal + item_2.subtotal
    db.add_all([item_1, item_2])
    db.add(venda)
    db.commit()

    response = client.get(
        "/relatorios/vendas",
        params={**_periodo_hoje(), "produto_id": produto.id},
        headers=auth_headers,
    )

    dados = response.json()

    # receita_total é da venda inteira (contém o produto filtrado)
    assert dados["receita_total"]["atual"] == 55.0
    # mas produtos_vendidos/lucro só contam o produto filtrado
    assert dados["produtos_vendidos"]["atual"] == 2
    assert dados["lucro"]["atual"] == 20.0


def test_relatorio_vendas_top_produtos_e_formas_pagamento(
    client, auth_headers, db, produto
):
    _criar_venda(db, produto, quantidade=4, forma_pagamento="PIX")
    _criar_venda(db, produto, quantidade=1, forma_pagamento="DINHEIRO")

    response = client.get(
        "/relatorios/vendas",
        params=_periodo_hoje(),
        headers=auth_headers,
    )

    dados = response.json()

    assert len(dados["top_produtos"]) == 1
    assert dados["top_produtos"][0]["produto"] == produto.nome
    assert dados["top_produtos"][0]["quantidade"] == 5

    formas = {
        item["forma_pagamento"]: item for item in dados["formas_pagamento"]
    }
    assert formas["PIX"]["total"] == 80.0
    assert formas["DINHEIRO"]["total"] == 20.0


def test_relatorio_vendas_top_produtos_ordenar_por_valor(
    client, auth_headers, db, produto
):
    from app.models.produto import Produto

    # produto caro, vendido poucas vezes: maior valor total, menor
    # quantidade
    caro = Produto(
        codigo="P003",
        nome="Produto Caro",
        categoria="Geral",
        unidade="UN",
        preco_custo=50.0,
        preco_venda=100.0,
        estoque=50,
        estoque_minimo=5,
        ativo=True,
    )
    db.add(caro)
    db.commit()
    db.refresh(caro)

    # "produto" (fixture, preco_venda=20) vendido 10x = R$200/10un
    # "caro" (preco_venda=100) vendido 3x = R$300/3un
    # -> por quantidade o barato vence (10 > 3), por valor o caro vence
    # (300 > 200) -- cenário desenhado pra provar que o parâmetro
    # ordenar_por realmente troca o critério, não só o número de itens
    _criar_venda(db, produto, quantidade=10)
    _criar_venda(db, caro, quantidade=3)

    response = client.get(
        "/relatorios/vendas",
        params={
            **_periodo_hoje(),
            "top_produtos_ordenar_por": "quantidade",
        },
        headers=auth_headers,
    )
    dados = response.json()

    # por quantidade (padrão, usado pelo PDV/Dashboard): o barato vence
    assert dados["top_produtos"][0]["produto"] == produto.nome
    assert dados["top_produtos"][0]["quantidade"] == 10

    response = client.get(
        "/relatorios/vendas",
        params={
            **_periodo_hoje(),
            "top_produtos_ordenar_por": "valor",
            "top_produtos_limite": 10,
        },
        headers=auth_headers,
    )
    dados = response.json()

    # por valor (usado pelos Relatórios): o caro vence
    assert dados["top_produtos"][0]["produto"] == caro.nome
    assert dados["top_produtos"][0]["total"] == 300.0


def test_relatorio_vendas_tabela_detalhada_paginada(
    client, auth_headers, db, produto
):
    for _ in range(3):
        _criar_venda(db, produto, quantidade=1)

    response = client.get(
        "/relatorios/vendas",
        params={**_periodo_hoje(), "skip": 0, "limit": 2},
        headers=auth_headers,
    )

    dados = response.json()

    assert dados["vendas_total"] == 3
    assert len(dados["vendas"]) == 2


def test_relatorio_vendas_sem_periodo_retorna_erro(client, auth_headers):
    response = client.get("/relatorios/vendas", headers=auth_headers)

    assert response.status_code == 422


def test_comparativo_lojas_soma_cada_loja_separado(
    client, auth_headers, db, produto
):
    from app.models.loja import Loja

    matriz = Loja(nome="Matriz")
    filial = Loja(nome="Filial")
    db.add_all([matriz, filial])
    db.commit()

    venda_matriz = _criar_venda(db, produto, quantidade=2)
    venda_matriz.loja_id = matriz.id

    venda_filial = _criar_venda(db, produto, quantidade=1)
    venda_filial.loja_id = filial.id

    db.commit()

    response = client.get(
        "/relatorios/comparativo-lojas",
        params=_periodo_hoje(),
        headers=auth_headers,
    )

    assert response.status_code == 200
    dados = {item["loja_nome"]: item for item in response.json()}

    assert dados["Matriz"]["quantidade_vendas"] == 1
    assert dados["Matriz"]["receita_total"] == float(venda_matriz.valor_total)
    assert dados["Filial"]["quantidade_vendas"] == 1
    assert dados["Filial"]["receita_total"] == float(venda_filial.valor_total)


def test_funil_vendas_conta_finalizadas_canceladas_e_abertas(
    client, auth_headers, db, produto
):
    _criar_venda(db, produto, quantidade=1, status="FINALIZADA")
    _criar_venda(db, produto, quantidade=1, status="FINALIZADA")
    _criar_venda(db, produto, quantidade=1, status="CANCELADA")

    client.post(
        "/vendas/suspender",
        json={
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

    response = client.get(
        "/relatorios/funil-vendas",
        params=_periodo_hoje(),
        headers=auth_headers,
    )

    assert response.status_code == 200

    dados = response.json()
    assert dados["finalizadas"] == 2
    assert dados["canceladas"] == 1
    assert dados["suspensas_agora"] == 1
    assert float(dados["taxa_cancelamento"]) == round(1 / 3 * 100, 2)


def test_funil_vendas_fora_do_periodo_nao_conta(client, auth_headers, db, produto):
    _criar_venda(
        db, produto, quantidade=1, status="FINALIZADA",
        data=datetime.utcnow() - timedelta(days=10),
    )

    response = client.get(
        "/relatorios/funil-vendas",
        params=_periodo_hoje(),
        headers=auth_headers,
    )

    dados = response.json()
    assert dados["finalizadas"] == 0
    assert dados["canceladas"] == 0
