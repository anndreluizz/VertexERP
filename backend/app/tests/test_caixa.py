def test_abrir_caixa(client, auth_headers):
    response = client.post(
        "/caixa/abrir",
        json={"saldo_inicial": 100.0},
        headers=auth_headers,
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["status"] == "ABERTO"
    assert dados["saldo_inicial"] == 100.0
    assert dados["saldo_final"] == 100.0


def test_abrir_caixa_ja_existe_um_aberto(client, auth_headers, caixa_aberto):
    response = client.post(
        "/caixa/abrir",
        json={"saldo_inicial": 50.0},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Você já tem um caixa aberto."


def test_fechar_caixa(client, auth_headers, caixa_aberto):
    response = client.post(
        "/caixa/fechar", json={}, headers=auth_headers
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["status"] == "FECHADO"
    assert dados["data_fechamento"] is not None


def test_fechar_caixa_sem_caixa_aberto(client, auth_headers):
    response = client.post(
        "/caixa/fechar", json={}, headers=auth_headers
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Nenhum caixa aberto."


def test_caixa_aberto_sem_nenhum_aberto(client, auth_headers):
    response = client.get("/caixa/aberto", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() is None


def test_caixa_aberto_com_caixa_existente(client, auth_headers, caixa_aberto):
    response = client.get("/caixa/aberto", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["id"] == caixa_aberto.id


def test_historico_e_resumo_de_caixa_ja_fechado(client, auth_headers, caixa_aberto, usuario):
    client.post(
        "/movimentos-caixa/",
        json={"tipo": "SUPRIMENTO", "descricao": "Suprimento", "valor": 50.0},
        headers=auth_headers,
    )
    client.post("/caixa/fechar", json={"valor_contado": 150}, headers=auth_headers)

    historico = client.get("/caixa/historico?limite=60", headers=auth_headers).json()
    assert historico[0]["id"] == caixa_aberto.id
    assert historico[0]["usuario_nome"] == usuario.nome

    resumo = client.get(f"/caixa/{caixa_aberto.id}/resumo", headers=auth_headers)
    assert resumo.status_code == 200
    assert float(resumo.json()["suprimentos"]) == 50.0
    assert float(resumo.json()["total_previsto"]) == 150.0

    assert client.get("/caixa/999999/resumo", headers=auth_headers).status_code == 404


def test_entradas_soma_o_que_entrou_de_verdade(client, auth_headers, db, caixa_aberto, usuario):
    from datetime import datetime, timedelta
    from app.models.movimento_caixa import MovimentoCaixa

    hoje = datetime.now()
    for tipo, forma, valor, data in [
        ("VENDA", "DINHEIRO", 100, hoje),
        ("VENDA", "PIX", 50, hoje),
        ("VENDA", "DEBITO", 30, hoje),
        ("VENDA", "CREDITO", 20, hoje),
        ("ESTORNO", "PIX", -10, hoje),
        ("VENDA", "PRAZO", 80, hoje),
        ("RECEBIMENTO_FIADO", "DINHEIRO", 40, hoje),
        ("RECEBIMENTO_FIADO", "PIX", 60, hoje),
        ("RECEBIMENTO_FIADO", "CARTAO", 300, hoje),
        ("SUPRIMENTO", None, 500, hoje),
        ("SANGRIA", None, 25, hoje),
        ("VENDA", "DINHEIRO", 999, hoje - timedelta(days=40)),
    ]:
        db.add(MovimentoCaixa(
            caixa_id=caixa_aberto.id, usuario_id=usuario.id, tipo=tipo,
            forma_pagamento=forma, valor=valor, data=data,
        ))
    from app.models.conta_pagar import ContaPagar
    for status, valor, pago_em in [
        ("PAGO", 70, hoje), ("PAGO", 500, hoje - timedelta(days=40)), ("PENDENTE", 300, None),
    ]:
        db.add(ContaPagar(
            descricao="Luz", valor=valor, status=status, data_pagamento=pago_em,
            data_vencimento=hoje,
        ))
    db.commit()

    dia = hoje.date().isoformat()
    dados = client.get(f"/caixa/entradas?inicio={dia}&fim={dia}", headers=auth_headers).json()
    assert {k: float(v) for k, v in dados.items()} == {
        "dinheiro": 140.0, "pix": 100.0, "cartao": 350.0, "outros": 0.0,
        "fiado_recebido": 400.0, "total": 590.0, "sangrias": 25.0, "vendas_prazo": 80.0,
        "contas_pagas": 70.0, "sobrou": 495.0,
    }

    tudo = client.get("/caixa/entradas", headers=auth_headers).json()
    assert float(tudo["total"]) == 590.0 + 999


def test_resumo_separa_fiado_por_forma(client, auth_headers, cliente, caixa_aberto):
    for forma, valor in (("DINHEIRO", 10.0), ("PIX", 20.0), ("CARTAO", 30.0)):
        client.post(
            "/fiado/compra",
            json={"cliente_id": cliente.id, "valor": valor, "descricao": "x"},
            headers=auth_headers,
        )
        response = client.post(
            "/fiado/movimentos",
            json={
                "cliente_id": cliente.id,
                "tipo": "PAGAMENTO",
                "valor": valor,
                "descricao": "pagou",
                "forma_pagamento": forma,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text

    resumo = client.get("/caixa/resumo", headers=auth_headers).json()

    assert float(resumo["recebimentos_fiado"]) == 60.0
    assert float(resumo["recebimentos_fiado_dinheiro"]) == 10.0
    assert float(resumo["recebimentos_fiado_pix"]) == 20.0
    assert float(resumo["recebimentos_fiado_cartao"]) == 30.0
    assert float(resumo["recebimentos_fiado_outros"]) == 0.0
    assert float(resumo["contas_pagas_caixa"]) == 0.0
    # gaveta = troco + fiado em dinheiro; total = gaveta + pix + cartao
    saldo_inicial = float(caixa_aberto.saldo_inicial)
    assert float(resumo["total_previsto"]) == saldo_inicial + 10.0
    assert float(resumo["total_geral"]) == saldo_inicial + 60.0


def test_abrir_e_fechar_caixa_avisa_tambem_quem_fez(client, auth_headers, usuario, monkeypatch):
    # 19/10: o dono abre/fecha no PC e quer o aviso (com o valor) no celular
    from app.services.notificacao_service import NotificacaoService

    enviados = []
    monkeypatch.setattr(
        NotificacaoService, "enviar",
        lambda tokens, titulo, corpo, dados=None: enviados.append((titulo, corpo)),
    )

    client.post("/caixa/abrir", json={"saldo_inicial": 100}, headers=auth_headers)
    client.post("/caixa/fechar", json={}, headers=auth_headers)

    notificacoes = client.get("/notificacoes/?skip=0&limit=10", headers=auth_headers).json()
    titulos = [n["titulo"] for n in notificacoes]
    assert "Caixa aberto" in titulos and "Caixa fechado" in titulos
    assert "100" in enviados[0][1]


def test_caixa_aberto_mais_de_24h_bloqueia_operacao_mas_deixa_fechar(
    client, auth_headers, db, caixa_aberto
):
    from datetime import datetime, timedelta

    caixa_aberto.data_abertura = datetime.now() - timedelta(hours=25)
    db.commit()

    sangria = client.post(
        "/movimentos-caixa/",
        json={"tipo": "SANGRIA", "descricao": "Sangria", "valor": 10.0},
        headers=auth_headers,
    )
    assert sangria.status_code == 400
    assert "24 horas" in sangria.json()["detail"]

    fechar = client.post("/caixa/fechar", json={}, headers=auth_headers)
    assert fechar.status_code == 200

    from app.models.notificacao import Notificacao

    corpos = [n.corpo for n in db.query(Notificacao).filter(Notificacao.titulo == "Caixa fechado")]
    assert any("mais de 24 horas" in c for c in corpos)


def test_caixa_aberto_informa_vencido(client, auth_headers, db, caixa_aberto):
    from datetime import datetime, timedelta

    assert client.get("/caixa/aberto", headers=auth_headers).json()["vencido"] is False

    caixa_aberto.data_abertura = datetime.now() - timedelta(hours=25)
    db.commit()

    assert client.get("/caixa/aberto", headers=auth_headers).json()["vencido"] is True
