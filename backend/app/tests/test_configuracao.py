def test_buscar_configuracoes_cria_linha_padrao_em_branco(
    client, auth_headers
):
    response = client.get("/configuracoes/", headers=auth_headers)

    assert response.status_code == 200

    dados = response.json()

    assert dados["id"] == 1
    assert dados["nome_loja"] is None
    assert dados["pix_chave"] is None


def test_atualizar_configuracoes(client, auth_headers):
    response = client.put(
        "/configuracoes/",
        json={
            "nome_loja": "Mercadinho do André",
            "cnpj_cpf": "06070024257",
            "endereco": "Rua Principal, 123",
            "telefone": "(97) 99999-9999",
            "pix_chave": "06070024257",
            "pix_nome": "Andre Luis Coelho Lopes",
            "pix_cidade": "Tonantins",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["nome_loja"] == "Mercadinho do André"
    assert dados["pix_chave"] == "06070024257"

    # Persistiu de verdade — uma nova busca reflete o valor salvo.
    busca = client.get("/configuracoes/", headers=auth_headers).json()
    assert busca["nome_loja"] == "Mercadinho do André"


def test_atualizar_configuracoes_atualiza_so_os_campos_enviados(
    client, auth_headers
):
    client.put(
        "/configuracoes/",
        json={"nome_loja": "Loja A"},
        headers=auth_headers,
    )

    response = client.put(
        "/configuracoes/",
        json={"telefone": "(97) 98888-8888"},
        headers=auth_headers,
    )

    dados = response.json()

    assert dados["nome_loja"] == "Loja A"
    assert dados["telefone"] == "(97) 98888-8888"


def test_atualizar_configuracoes_exige_admin(client, auth_headers_comum):
    response = client.put(
        "/configuracoes/",
        json={"nome_loja": "Tentativa Operador"},
        headers=auth_headers_comum,
    )

    assert response.status_code == 403


def test_upload_logo_e_busca(client, auth_headers):
    # Logo é salvo via base64 no PUT genérico, mesmo padrão de
    # Cliente.foto_base64 -- não existe upload multipart dedicado.
    import base64

    conteudo_png = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
        b"\x1c\xe7\x93\xa1\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    response = client.put(
        "/configuracoes/",
        json={
            "logo_filename": "logo.png",
            "logo_base64": base64.b64encode(conteudo_png).decode("ascii"),
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["logo_filename"] == "logo.png"
    assert response.json()["tem_logo"] is True

    busca = client.get("/configuracoes/logo", headers=auth_headers)

    assert busca.status_code == 200
    assert busca.content == conteudo_png


def test_buscar_logo_sem_logo_cadastrada(client, auth_headers):
    response = client.get("/configuracoes/logo", headers=auth_headers)

    assert response.status_code == 404


def test_renomear_e_desativar_loja(client, auth_headers, db):
    from app.models.caixa import Caixa
    from app.models.loja import Loja

    a, b = Loja(nome="Matriz T"), Loja(nome="filial t")
    db.add_all([a, b])
    db.commit()

    r = client.put(f"/lojas/{b.id}", json={"nome": " Filial T "}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["nome"] == "Filial T"

    r = client.put(f"/lojas/{b.id}", json={"nome": "Matriz T"}, headers=auth_headers)
    assert r.status_code == 400

    db.add(Caixa(loja_id=b.id, saldo_inicial=0, status="ABERTO"))
    db.commit()
    r = client.put(f"/lojas/{b.id}", json={"ativa": False}, headers=auth_headers)
    assert r.status_code == 400 and "caixa aberto" in r.json()["detail"]

    db.query(Caixa).filter(Caixa.loja_id == b.id).update({"status": "FECHADO"})
    db.commit()
    r = client.put(f"/lojas/{b.id}", json={"ativa": False}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["ativa"] is False

    assert client.put("/lojas/99999", json={"nome": "X"}, headers=auth_headers).status_code == 404
