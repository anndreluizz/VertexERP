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
