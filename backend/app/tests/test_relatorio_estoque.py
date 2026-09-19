from datetime import datetime

from app.models.venda import Venda
from app.models.item_venda import ItemVenda
from app.models.produto import Produto
from app.models.loja import Loja
from app.models.estoque_loja import EstoqueLoja


def _criar_venda_item(db, produto, valor_unitario, quantidade=1):
    venda = Venda(
        valor_total=valor_unitario * quantidade,
        desconto=0,
        forma_pagamento="DINHEIRO",
        status="FINALIZADA",
        data=datetime.utcnow(),
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


def _criar_produto(db, codigo, nome):
    p = Produto(
        codigo=codigo,
        nome=nome,
        categoria="Geral",
        unidade="UN",
        preco_custo=1.0,
        preco_venda=1.0,
        estoque=0,
        estoque_minimo=0,
        ativo=True,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _periodo_hoje():
    hoje = datetime.utcnow().date().isoformat()
    return {"data_inicio": hoje, "data_fim": hoje}


def test_curva_abc_classifica_80_95_100(client, auth_headers, db):
    produto_a = _criar_produto(db, "ABC-A", "Produto A")
    produto_b = _criar_produto(db, "ABC-B", "Produto B")
    produto_c = _criar_produto(db, "ABC-C", "Produto C")

    # receita total = 100; A=80%, B=+15% (acumulado 95%), C=+5% (100%)
    _criar_venda_item(db, produto_a, valor_unitario=80)
    _criar_venda_item(db, produto_b, valor_unitario=15)
    _criar_venda_item(db, produto_c, valor_unitario=5)

    response = client.get(
        "/relatorios/curva-abc", params=_periodo_hoje(), headers=auth_headers
    )

    assert response.status_code == 200
    itens = response.json()

    por_produto = {i["produto"]: i for i in itens}

    assert por_produto["Produto A"]["classe"] == "A"
    assert por_produto["Produto A"]["percentual_acumulado"] == 80.0

    assert por_produto["Produto B"]["classe"] == "B"
    assert por_produto["Produto B"]["percentual_acumulado"] == 95.0

    assert por_produto["Produto C"]["classe"] == "C"
    assert por_produto["Produto C"]["percentual_acumulado"] == 100.0


def test_curva_abc_sem_vendas_no_periodo_retorna_vazio(client, auth_headers):
    response = client.get(
        "/relatorios/curva-abc", params=_periodo_hoje(), headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json() == []


def test_comparativo_estoque_bate_com_estoque_loja(client, auth_headers, db):
    loja_a = Loja(nome="Loja Estoque Comparativo A")
    loja_b = Loja(nome="Loja Estoque Comparativo B")
    db.add_all([loja_a, loja_b])
    db.commit()

    produto = Produto(
        codigo="CMP-001",
        nome="Produto Comparativo",
        categoria="Geral",
        unidade="UN",
        preco_custo=10.0,
        preco_venda=20.0,
        estoque=0,
        estoque_minimo=5,
        ativo=True,
    )
    db.add(produto)
    db.commit()
    db.refresh(produto)

    db.add(
        EstoqueLoja(
            produto_id=produto.id, loja_id=loja_a.id,
            quantidade=20, estoque_minimo=5,
        )
    )
    db.add(
        EstoqueLoja(
            produto_id=produto.id, loja_id=loja_b.id,
            quantidade=2, estoque_minimo=5,
        )
    )
    db.commit()

    response = client.get("/relatorios/comparativo-estoque", headers=auth_headers)

    assert response.status_code == 200
    por_loja = {item["loja_id"]: item for item in response.json()}

    assert por_loja[loja_a.id]["quantidade_total"] == 20
    assert float(por_loja[loja_a.id]["valor_em_estoque"]) == 200.0
    assert por_loja[loja_a.id]["produtos_abaixo_minimo"] == 0

    assert por_loja[loja_b.id]["quantidade_total"] == 2
    assert float(por_loja[loja_b.id]["valor_em_estoque"]) == 20.0
    assert por_loja[loja_b.id]["produtos_abaixo_minimo"] == 1


def test_sugestao_reposicao_por_loja_lista_so_abaixo_do_minimo(
    client, auth_headers, db
):
    loja = Loja(nome="Loja Reposicao")
    db.add(loja)
    db.commit()

    baixo = _criar_produto(db, "REP-BAIXO", "Produto Baixo")
    ok = _criar_produto(db, "REP-OK", "Produto OK")

    db.add(
        EstoqueLoja(
            produto_id=baixo.id, loja_id=loja.id,
            quantidade=2, estoque_minimo=10,
        )
    )
    db.add(
        EstoqueLoja(
            produto_id=ok.id, loja_id=loja.id,
            quantidade=50, estoque_minimo=10,
        )
    )
    db.commit()

    response = client.get(
        f"/relatorios/sugestao-reposicao?loja_id={loja.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    itens = response.json()

    assert len(itens) == 1
    assert itens[0]["produto"] == "Produto Baixo"
    assert itens[0]["quantidade_sugerida"] == 8


def test_sugestao_reposicao_sem_loja_usa_produto_global(client, auth_headers, db):
    produto = Produto(
        codigo="REP-GLOBAL",
        nome="Produto Global Baixo",
        categoria="Geral",
        unidade="UN",
        preco_custo=1.0,
        preco_venda=2.0,
        estoque=1,
        estoque_minimo=10,
        ativo=True,
    )
    db.add(produto)
    db.commit()

    response = client.get("/relatorios/sugestao-reposicao", headers=auth_headers)

    assert response.status_code == 200
    nomes = [i["produto"] for i in response.json()]
    assert "Produto Global Baixo" in nomes
