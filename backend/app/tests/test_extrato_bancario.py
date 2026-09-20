def _ofx(transacoes):
    """transacoes: list of (fitid, data_yyyymmdd, valor, memo)"""

    linhas = ["<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>",
              "<BANKACCTFROM><BANKID>001<ACCTID>12345-6</BANKACCTFROM>",
              "<BANKTRANLIST>"]

    for fitid, data, valor, memo in transacoes:
        linhas.append(
            f"<STMTTRN><TRNTYPE>{'CREDIT' if float(valor) >= 0 else 'DEBIT'}"
            f"<DTPOSTED>{data}120000[-3:BRT]"
            f"<TRNAMT>{valor}"
            f"<FITID>{fitid}"
            f"<MEMO>{memo}"
            f"</STMTTRN>"
        )

    linhas.append("</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>")
    return "\n".join(linhas)


def test_preview_extrai_transacoes(client, auth_headers):
    conteudo = _ofx([
        ("FIT001", "20261201", "-150.00", "PAGAMENTO BOLETO"),
        ("FIT002", "20261202", "500.00", "DEPOSITO"),
    ])

    response = client.post(
        "/extrato-bancario/preview",
        json={"ofx_conteudo": conteudo},
        headers=auth_headers,
    )

    assert response.status_code == 200
    dados = response.json()
    assert dados["total_novas"] == 2
    assert dados["total_ja_importadas"] == 0
    tipos = {t["fitid"]: t["tipo"] for t in dados["transacoes"]}
    assert tipos["FIT001"] == "DEBITO"
    assert tipos["FIT002"] == "CREDITO"


def test_importar_persiste_e_evita_duplicata(client, auth_headers):
    conteudo = _ofx([("FIT100", "20261201", "-80.00", "TARIFA")])

    primeira = client.post(
        "/extrato-bancario/importar",
        json={"ofx_conteudo": conteudo},
        headers=auth_headers,
    )
    assert primeira.status_code == 200
    assert primeira.json()["total_importadas"] == 1

    segunda = client.post(
        "/extrato-bancario/importar",
        json={"ofx_conteudo": conteudo},
        headers=auth_headers,
    )
    assert segunda.status_code == 200
    assert segunda.json()["total_importadas"] == 0

    listagem = client.get("/extrato-bancario/", headers=auth_headers).json()
    assert len([t for t in listagem if t["fitid"] == "FIT100"]) == 1


def test_sugerir_e_conciliar_com_conta_pagar(client, auth_headers):
    conta_pagar = client.post(
        "/contas-pagar/",
        json={
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": "150.00",
            "descricao": "Aluguel",
        },
        headers=auth_headers,
    ).json()
    pago = client.post(
        f"/contas-pagar/{conta_pagar['id']}/pagar", headers=auth_headers
    ).json()

    data_pagamento_yyyymmdd = pago["data_pagamento"][:10].replace("-", "")

    conteudo = _ofx([
        ("FIT200", data_pagamento_yyyymmdd, "-150.00", "PAGTO ALUGUEL"),
    ])
    client.post(
        "/extrato-bancario/importar",
        json={"ofx_conteudo": conteudo},
        headers=auth_headers,
    )

    transacao = next(
        t for t in client.get(
            "/extrato-bancario/", headers=auth_headers
        ).json()
        if t["fitid"] == "FIT200"
    )

    sugestoes = client.get(
        f"/extrato-bancario/{transacao['id']}/sugestoes",
        headers=auth_headers,
    ).json()
    assert any(s["id"] == conta_pagar["id"] for s in sugestoes)

    conciliada = client.post(
        f"/extrato-bancario/{transacao['id']}/conciliar",
        json={"conta_pagar_id": conta_pagar["id"]},
        headers=auth_headers,
    )
    assert conciliada.status_code == 200
    assert conciliada.json()["status"] == "CONCILIADA"
    assert conciliada.json()["conta_pagar_id"] == conta_pagar["id"]


def test_conciliar_tipo_errado_falha(client, auth_headers):
    conta_pagar = client.post(
        "/contas-pagar/",
        json={
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": "50.00",
        },
        headers=auth_headers,
    ).json()
    client.post(
        f"/contas-pagar/{conta_pagar['id']}/pagar", headers=auth_headers
    )

    conteudo = _ofx([("FIT300", "20261201", "500.00", "ENTRADA")])
    client.post(
        "/extrato-bancario/importar",
        json={"ofx_conteudo": conteudo},
        headers=auth_headers,
    )
    transacao = next(
        t for t in client.get(
            "/extrato-bancario/", headers=auth_headers
        ).json()
        if t["fitid"] == "FIT300"
    )

    # transacao e' CREDITO (entrada), tentando conciliar com conta a
    # pagar (que so' aceita DEBITO) deve falhar
    response = client.post(
        f"/extrato-bancario/{transacao['id']}/conciliar",
        json={"conta_pagar_id": conta_pagar["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_conciliar_conta_ja_linkada_falha(client, auth_headers):
    conta_pagar = client.post(
        "/contas-pagar/",
        json={
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": "60.00",
        },
        headers=auth_headers,
    ).json()
    pago = client.post(
        f"/contas-pagar/{conta_pagar['id']}/pagar", headers=auth_headers
    ).json()
    data_yyyymmdd = pago["data_pagamento"][:10].replace("-", "")

    conteudo = _ofx([
        ("FIT600", data_yyyymmdd, "-60.00", "PAGTO A"),
        ("FIT601", data_yyyymmdd, "-60.00", "PAGTO B"),
    ])
    client.post(
        "/extrato-bancario/importar",
        json={"ofx_conteudo": conteudo},
        headers=auth_headers,
    )
    transacoes = {
        t["fitid"]: t
        for t in client.get(
            "/extrato-bancario/", headers=auth_headers
        ).json()
        if t["fitid"] in ("FIT600", "FIT601")
    }

    primeira = client.post(
        f"/extrato-bancario/{transacoes['FIT600']['id']}/conciliar",
        json={"conta_pagar_id": conta_pagar["id"]},
        headers=auth_headers,
    )
    assert primeira.status_code == 200

    segunda = client.post(
        f"/extrato-bancario/{transacoes['FIT601']['id']}/conciliar",
        json={"conta_pagar_id": conta_pagar["id"]},
        headers=auth_headers,
    )
    assert segunda.status_code == 400


def test_ignorar_e_desconciliar(client, auth_headers):
    conteudo = _ofx([("FIT400", "20261201", "-30.00", "TARIFA BANCARIA")])
    client.post(
        "/extrato-bancario/importar",
        json={"ofx_conteudo": conteudo},
        headers=auth_headers,
    )
    transacao = next(
        t for t in client.get(
            "/extrato-bancario/", headers=auth_headers
        ).json()
        if t["fitid"] == "FIT400"
    )

    ignorada = client.post(
        f"/extrato-bancario/{transacao['id']}/ignorar", headers=auth_headers
    )
    assert ignorada.status_code == 200
    assert ignorada.json()["status"] == "IGNORADA"

    # nao pode conciliar nem ignorar de novo uma ja ignorada
    resposta = client.post(
        f"/extrato-bancario/{transacao['id']}/ignorar", headers=auth_headers
    )
    assert resposta.status_code == 400


def test_conciliar_receber(client, auth_headers, cliente, caixa_aberto):
    conta_receber = client.post(
        "/contas-receber/",
        json={
            "cliente_id": cliente.id,
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": 300.0,
        },
        headers=auth_headers,
    ).json()
    recebida = client.post(
        f"/contas-receber/{conta_receber['id']}/receber",
        headers=auth_headers,
    ).json()

    data_yyyymmdd = recebida["data_recebimento"][:10].replace("-", "")

    conteudo = _ofx([("FIT500", data_yyyymmdd, "300.00", "RECEBIMENTO")])
    client.post(
        "/extrato-bancario/importar",
        json={"ofx_conteudo": conteudo},
        headers=auth_headers,
    )
    transacao = next(
        t for t in client.get(
            "/extrato-bancario/", headers=auth_headers
        ).json()
        if t["fitid"] == "FIT500"
    )

    response = client.post(
        f"/extrato-bancario/{transacao['id']}/conciliar",
        json={"conta_receber_id": conta_receber["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["conta_receber_id"] == conta_receber["id"]

    desfeita = client.post(
        f"/extrato-bancario/{transacao['id']}/desconciliar",
        headers=auth_headers,
    )
    assert desfeita.status_code == 200
    assert desfeita.json()["status"] == "PENDENTE"
