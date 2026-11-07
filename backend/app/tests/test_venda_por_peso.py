"""Produto em KG: vende 0,347 kg, baixa estoque fracionado e o subtotal
arredonda no centavo (meio pra cima). Produto UN continua inteiro."""
from decimal import Decimal

import pytest


@pytest.fixture()
def picanha(db):
    from app.models.produto import Produto

    novo = Produto(
        codigo="0007", nome="PICANHA", categoria="Acougue", unidade="KG",
        preco_custo=30, preco_venda=Decimal("39.90"), estoque=Decimal("12.5"),
        estoque_minimo=1, ativo=True,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


def _vender(client, auth_headers, produto_id, quantidade, valor):
    return client.post(
        "/vendas/",
        json={"forma_pagamento": "DINHEIRO", "itens": [
            {"produto_id": produto_id, "quantidade": quantidade, "valor_unitario": valor},
        ]},
        headers=auth_headers,
    )


def test_venda_por_kg_baixa_estoque_fracionado(client, auth_headers, picanha, caixa_aberto):
    resposta = _vender(client, auth_headers, picanha.id, 0.347, "39.90")

    assert resposta.status_code == 201, resposta.text
    dados = resposta.json()
    assert float(dados["valor_total"]) == 13.85  # 13,8453
    assert dados["itens"][0]["quantidade"] == 0.347

    produto = client.get(f"/produtos/{picanha.id}", headers=auth_headers).json()
    assert produto["estoque"] == 12.153

    pdv = client.get("/pdv/produto/0007", headers=auth_headers).json()
    assert pdv["unidade"] == "KG"
    assert pdv["estoque"] == 12.153


def test_venda_por_kg_acima_do_estoque_e_recusada(client, auth_headers, picanha, caixa_aberto):
    resposta = _vender(client, auth_headers, picanha.id, 12.501, "39.90")
    assert resposta.status_code == 400


def test_produto_por_unidade_recusa_quantidade_com_virgula(
    client, auth_headers, produto, caixa_aberto
):
    resposta = _vender(client, auth_headers, produto.id, 1.5, "20.00")

    assert resposta.status_code == 400
    assert "vendido por unidade" in resposta.json()["detail"]


def test_quantidade_inteira_continua_saindo_como_inteiro(
    client, auth_headers, produto, caixa_aberto
):
    resposta = _vender(client, auth_headers, produto.id, 2, "20.00")

    assert resposta.status_code == 201
    assert resposta.json()["itens"][0]["quantidade"] == 2
    produto_json = client.get(f"/produtos/{produto.id}", headers=auth_headers).json()
    assert produto_json["estoque"] == 48
    assert isinstance(produto_json["estoque"], int)


def test_formatar_quantidade():
    from app.utils.quantidade import formatar_quantidade

    assert formatar_quantidade(Decimal("0.35"), "KG") == "0,350 kg"
    assert formatar_quantidade(Decimal("5.000"), "UN") == "5"
