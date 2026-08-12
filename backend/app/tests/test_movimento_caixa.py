def test_criar_movimento_sem_caixa_aberto(client, auth_headers):
    response = client.post(
        "/movimentos-caixa/",
        json={"tipo": "SUPRIMENTO", "descricao": "Suprimento", "valor": 50.0},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Não existe caixa aberto."


def test_movimento_suprimento_aumenta_saldo(client, auth_headers, caixa_aberto):
    response = client.post(
        "/movimentos-caixa/",
        json={"tipo": "SUPRIMENTO", "descricao": "Suprimento", "valor": 50.0},
        headers=auth_headers,
    )

    assert response.status_code == 200

    caixa = client.get("/caixa/aberto", headers=auth_headers).json()

    assert caixa["saldo_final"] == caixa_aberto.saldo_inicial + 50.0


def test_movimento_sangria_diminui_saldo(client, auth_headers, caixa_aberto):
    response = client.post(
        "/movimentos-caixa/",
        json={"tipo": "SANGRIA", "descricao": "Sangria", "valor": 30.0},
        headers=auth_headers,
    )

    assert response.status_code == 200

    caixa = client.get("/caixa/aberto", headers=auth_headers).json()

    assert caixa["saldo_final"] == caixa_aberto.saldo_inicial - 30.0


def test_listar_movimentos(client, auth_headers, caixa_aberto):
    client.post(
        "/movimentos-caixa/",
        json={"tipo": "SUPRIMENTO", "descricao": "Suprimento", "valor": 50.0},
        headers=auth_headers,
    )

    response = client.get("/movimentos-caixa/", headers=auth_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_listar_movimentos_por_caixa(client, auth_headers, caixa_aberto):
    client.post(
        "/movimentos-caixa/",
        json={"tipo": "SUPRIMENTO", "descricao": "Suprimento", "valor": 50.0},
        headers=auth_headers,
    )

    response = client.get(
        f"/movimentos-caixa/caixa/{caixa_aberto.id}", headers=auth_headers
    )

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_listar_movimentos_por_tipo(client, auth_headers, caixa_aberto):
    client.post(
        "/movimentos-caixa/",
        json={"tipo": "SUPRIMENTO", "descricao": "Suprimento", "valor": 50.0},
        headers=auth_headers,
    )
    client.post(
        "/movimentos-caixa/",
        json={"tipo": "SANGRIA", "descricao": "Sangria", "valor": 10.0},
        headers=auth_headers,
    )

    response = client.get(
        "/movimentos-caixa/tipo/sangria", headers=auth_headers
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["tipo"] == "SANGRIA"
