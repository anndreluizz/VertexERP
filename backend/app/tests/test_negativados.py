"""Cliente negativado: divida baixada como perda (sai do fiado em
aberto, fica no historico) e nada pode ser vendido pra ele -- nem a
vista. So' admin negativa/desbloqueia."""

from datetime import datetime, timedelta

from app.models.movimento_fiado import MovimentoFiado


def _fiado(db, cliente, usuario, tipo, valor, dias_atras=0):
    m = MovimentoFiado(cliente_id=cliente.id, usuario_id=usuario.id, tipo=tipo,
                       valor=valor, data=datetime.now() - timedelta(days=dias_atras))
    db.add(m)
    db.commit()
    return m


def _saldo(client, headers, cliente):
    return client.get(f"/fiado/cliente/{cliente.id}", headers=headers).json()["saldo_devedor"]


def _venda(client, headers, produto, cliente, forma="DINHEIRO"):
    return client.post("/vendas/", json={
        "cliente_id": cliente.id, "forma_pagamento": forma,
        "data_vencimento": "2026-12-31T00:00:00",
        "itens": [{"produto_id": produto.id, "quantidade": 1, "valor_unitario": "20.00"}],
    }, headers=headers)


def test_negativar_baixa_divida_e_bloqueia_tudo(
    client, auth_headers, db, usuario, cliente, produto, caixa_aberto
):
    _fiado(db, cliente, usuario, "COMPRA", 100, dias_atras=400)

    r = client.post(f"/clientes/{cliente.id}/negativar",
                    json={"motivo": "ficha antiga"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["negativado"] is True
    assert float(_saldo(client, auth_headers, cliente)) == 0
    perda = db.query(MovimentoFiado).filter_by(cliente_id=cliente.id, tipo="PERDA").one()
    assert float(perda.valor) == 100

    assert client.post(f"/clientes/{cliente.id}/negativar", json={"motivo": "x"},
                       headers=auth_headers).status_code == 400

    # nada pode ser vendido: nem a vista, nem a prazo, nem compra manual no fiado
    for forma in ("DINHEIRO", "PRAZO"):
        r = _venda(client, auth_headers, produto, cliente, forma)
        assert r.status_code == 400 and "NEGATIVADO" in r.json()["detail"]
    r = client.post("/vendas/suspender", json={
        "cliente_id": cliente.id,
        "itens": [{"produto_id": produto.id, "quantidade": 1, "valor_unitario": "20.00"}],
    }, headers=auth_headers)
    assert r.status_code == 400
    r = client.post("/fiado/compra", json={"cliente_id": cliente.id, "valor": 10},
                    headers=auth_headers)
    assert r.status_code == 400
    # venda sem cliente continua normal
    r = client.post("/vendas/", json={"forma_pagamento": "DINHEIRO", "itens": [
        {"produto_id": produto.id, "quantidade": 1, "valor_unitario": "20.00"}]},
        headers=auth_headers)
    assert r.status_code == 201

    # desbloquear: volta a vender; a perda continua baixada
    r = client.post(f"/clientes/{cliente.id}/desbloquear", headers=auth_headers)
    assert r.json()["negativado"] is False
    assert _venda(client, auth_headers, produto, cliente).status_code == 201
    assert float(_saldo(client, auth_headers, cliente)) == 0


def test_so_admin_negativa(client, auth_headers_comum, cliente):
    assert client.post(f"/clientes/{cliente.id}/negativar", json={"motivo": "x"},
                       headers=auth_headers_comum).status_code == 403
    assert client.post(f"/clientes/{cliente.id}/desbloquear",
                       headers=auth_headers_comum).status_code == 403


def test_recuperar_divida_excluindo_a_perda(client, auth_headers, db, usuario, cliente):
    _fiado(db, cliente, usuario, "COMPRA", 80)
    client.post(f"/clientes/{cliente.id}/negativar", json={"motivo": "x"}, headers=auth_headers)
    perda = db.query(MovimentoFiado).filter_by(cliente_id=cliente.id, tipo="PERDA").one()

    r = client.delete(f"/fiado/movimentos/{perda.id}", headers=auth_headers)

    assert r.status_code == 200
    assert float(_saldo(client, auth_headers, cliente)) == 80


def test_bi_trata_como_perda_e_sugere_baixa(client, auth_headers, db, usuario, cliente):
    from app.models.cliente import Cliente

    parado = Cliente(nome="Parado", email="p@x.com", ativo=True)
    ativo = Cliente(nome="Ativo", email="a@x.com", ativo=True)
    db.add_all([parado, ativo])
    db.commit()
    _fiado(db, parado, usuario, "COMPRA", 70, dias_atras=500)
    _fiado(db, ativo, usuario, "COMPRA", 30, dias_atras=10)
    _fiado(db, cliente, usuario, "COMPRA", 100, dias_atras=600)
    client.post(f"/clientes/{cliente.id}/negativar", json={"motivo": "x"}, headers=auth_headers)

    hoje = datetime.now().date().isoformat()
    dados = client.get(f"/bi/resumo?data_inicio={hoje}&data_fim={hoje}",
                       headers=auth_headers).json()
    fiado = dados["fiado"]

    assert float(fiado["saldo_em_aberto"]) == 100  # parado + ativo, sem o negativado
    assert float(fiado["perdas_total"]) == 100
    assert fiado["clientes_negativados"] == 1
    assert [c["nome"] for c in fiado["sugestao_baixa"]] == ["Parado"]
    assert any(r["problema"].startswith("Dívidas paradas") for r in dados["recomendacoes"])
