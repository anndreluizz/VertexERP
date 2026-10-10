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
