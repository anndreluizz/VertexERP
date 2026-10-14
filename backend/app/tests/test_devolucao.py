"""Devolução parcial de venda (POST /vendas/{id}/devolucoes) e resumo
de vendas por vendedora (GET /vendas/resumo-vendedores)."""
from datetime import date
from decimal import Decimal


def _vender(client, auth_headers, produto, quantidade=3, **extra):
    corpo = {
        "forma_pagamento": "DINHEIRO",
        "itens": [
            {
                "produto_id": produto.id,
                "quantidade": quantidade,
                "valor_unitario": "20.00",
            }
        ],
    }
    corpo.update(extra)
    response = client.post("/vendas/", json=corpo, headers=auth_headers)
    assert response.status_code == 201, response.text
    return response.json()


def _devolver(client, auth_headers, venda, quantidade, forma="DINHEIRO"):
    return client.post(
        f"/vendas/{venda['id']}/devolucoes",
        json={
            "itens": [
                {"item_venda_id": venda["itens"][0]["id"], "quantidade": quantidade}
            ],
            "forma_reembolso": forma,
            "motivo": "Tamanho errado",
        },
        headers=auth_headers,
    )


def test_devolucao_parcial_devolve_estoque_e_tira_dinheiro_do_caixa(
    client, auth_headers, produto, caixa_aberto
):
    venda = _vender(client, auth_headers, produto, quantidade=3)

    response = _devolver(client, auth_headers, venda, 1)

    assert response.status_code == 200, response.text
    dados = response.json()
    assert Decimal(dados["valor_total"]) == Decimal("20.00")
    assert dados["itens"][0]["produto_nome"] == "Produto Teste"

    estoque = client.get(f"/produtos/{produto.id}", headers=auth_headers).json()["estoque"]
    assert estoque == 50 - 3 + 1

    caixa = client.get("/caixa/aberto", headers=auth_headers).json()
    assert caixa["saldo_final"] == 100.0 + 60.0 - 20.0

    # a venda continua valendo -- só os itens devolvidos voltaram
    venda_depois = client.get(f"/vendas/{venda['id']}", headers=auth_headers).json()
    assert venda_depois["status"] == "FINALIZADA"


def test_devolucao_rateia_o_desconto_da_venda(
    client, auth_headers, produto, caixa_aberto
):
    # 2 x 20 = 40, desconto 10 -> pagou 30, cada peça saiu por 15
    venda = _vender(client, auth_headers, produto, quantidade=2, desconto="10.00")

    response = _devolver(client, auth_headers, venda, 1)

    assert Decimal(response.json()["valor_total"]) == Decimal("15.00")


def test_nao_devolve_mais_do_que_foi_vendido(
    client, auth_headers, produto, caixa_aberto
):
    venda = _vender(client, auth_headers, produto, quantidade=2)

    assert _devolver(client, auth_headers, venda, 1).status_code == 200
    assert _devolver(client, auth_headers, venda, 1).status_code == 200

    terceira = _devolver(client, auth_headers, venda, 1)

    assert terceira.status_code == 400
    assert "só restam 0" in terceira.json()["detail"]

    devolucoes = client.get(
        f"/vendas/{venda['id']}/devolucoes", headers=auth_headers
    ).json()
    assert len(devolucoes) == 2


def test_devolucao_de_venda_fiado_abate_do_fiado(
    client, auth_headers, db, produto, cliente, caixa_aberto
):
    from app.repositories.movimento_fiado_repository import MovimentoFiadoRepository

    venda = _vender(
        client, auth_headers, produto, quantidade=2,
        forma_pagamento="PRAZO", cliente_id=cliente.id,
    )
    assert MovimentoFiadoRepository.saldo_por_cliente(db, cliente.id) == Decimal("40.00")

    response = _devolver(client, auth_headers, venda, 1, forma="PRAZO")

    assert response.status_code == 200, response.text
    db.expire_all()
    assert MovimentoFiadoRepository.saldo_por_cliente(db, cliente.id) == Decimal("20.00")

    # fiado não mexe na gaveta
    caixa = client.get("/caixa/aberto", headers=auth_headers).json()
    assert caixa["saldo_final"] == 100.0


def test_abater_do_fiado_exige_cliente_na_venda(
    client, auth_headers, produto, caixa_aberto
):
    venda = _vender(client, auth_headers, produto, quantidade=1)

    response = _devolver(client, auth_headers, venda, 1, forma="PRAZO")

    assert response.status_code == 400


def test_venda_com_devolucao_nao_pode_ser_cancelada_inteira(
    client, auth_headers, produto, caixa_aberto
):
    venda = _vender(client, auth_headers, produto, quantidade=2)
    _devolver(client, auth_headers, venda, 1)

    response = client.delete(f"/vendas/{venda['id']}", headers=auth_headers)

    assert response.status_code == 400
    assert "devolução" in response.json()["detail"]


def test_devolucao_exige_permissao(
    client, auth_headers, auth_headers_comum, produto, caixa_aberto
):
    venda = _vender(client, auth_headers, produto, quantidade=1)

    response = _devolver(client, auth_headers_comum, venda, 1)

    assert response.status_code == 403


def test_resumo_vendedores_desconta_devolucoes(
    client, auth_headers, produto, caixa_aberto
):
    venda = _vender(client, auth_headers, produto, quantidade=3)
    _vender(client, auth_headers, produto, quantidade=1)
    _devolver(client, auth_headers, venda, 1)

    hoje = date.today().isoformat()
    response = client.get(
        f"/vendas/resumo-vendedores?data_inicio={hoje}&data_fim={hoje}",
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    [linha] = response.json()
    assert linha["usuario_nome"] == "Usuário Teste"
    assert linha["quantidade_vendas"] == 2
    assert Decimal(linha["total_vendido"]) == Decimal("80.00")
    assert Decimal(linha["total_devolvido"]) == Decimal("20.00")
    assert Decimal(linha["total_liquido"]) == Decimal("60.00")


def test_listar_vendas_filtra_por_periodo_e_vendedor(
    client, auth_headers, usuario, produto, caixa_aberto
):
    _vender(client, auth_headers, produto, quantidade=1)

    hoje = date.today().isoformat()
    do_usuario = client.get(
        f"/vendas/?data_inicio={hoje}&data_fim={hoje}&usuario_id={usuario.id}",
        headers=auth_headers,
    ).json()
    de_outro = client.get(
        f"/vendas/?usuario_id={usuario.id + 999}", headers=auth_headers
    ).json()
    de_ontem = client.get(
        "/vendas/?data_inicio=2020-01-01&data_fim=2020-01-02", headers=auth_headers
    ).json()

    assert len(do_usuario) == 1
    assert de_outro == []
    assert de_ontem == []


def test_estoque_total_do_produto_acompanha_a_loja(db, produto):
    """Bug antigo: com loja cadastrada, produto.estoque era recalculado
    antes do flush e ficava sempre uma operação atrasado."""
    from app.models.loja import Loja
    from app.repositories.estoque_loja_repository import EstoqueLojaRepository

    loja = Loja(nome="Matriz", ativa=True)
    db.add(loja)
    db.commit()

    EstoqueLojaRepository.ajustar(db, produto, loja.id, 10)
    db.commit()
    assert produto.estoque == 10

    EstoqueLojaRepository.ajustar(db, produto, loja.id, -2)
    db.commit()
    assert produto.estoque == 8

    EstoqueLojaRepository.ajustar(db, produto, loja.id, 1)
    db.commit()
    assert produto.estoque == 9


def test_relatorio_de_vendas_desconta_devolucao(
    client, auth_headers, produto, caixa_aberto
):
    # 3 x R$ 20 = R$ 60, devolve 1 -> o relatorio mostra R$ 40 (igual
    # a tela de Vendas), e o grafico/formas de pagamento batem com isso
    venda = _vender(client, auth_headers, produto, quantidade=3)
    assert _devolver(client, auth_headers, venda, 1).status_code == 200

    hoje = date.today().isoformat()
    rel = client.get(
        "/relatorios/vendas",
        params={"data_inicio": hoje, "data_fim": hoje},
        headers=auth_headers,
    ).json()

    assert float(rel["receita_total"]["atual"]) == 40.0
    assert rel["produtos_vendidos"]["atual"] == 2
    assert sum(d["total"] for d in rel["vendas_por_dia"]) == 40.0
    assert sum(f["total"] for f in rel["formas_pagamento"]) == 40.0
