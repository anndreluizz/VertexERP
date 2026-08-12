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


def test_upload_logo_e_busca(client, auth_headers, tmp_path, monkeypatch):
    import app.services.configuracao_service as configuracao_service

    monkeypatch.setattr(
        configuracao_service, "DIRETORIO_UPLOADS", str(tmp_path)
    )

    conteudo_png = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0\x00\x00\x00\x03\x00\x01"
        b"\x1c\xe7\x93\xa1\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    response = client.post(
        "/configuracoes/logo",
        files={"arquivo": ("logo.png", conteudo_png, "image/png")},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["logo_filename"] == "logo.png"

    busca = client.get("/configuracoes/logo", headers=auth_headers)

    assert busca.status_code == 200
    assert busca.content == conteudo_png


def test_upload_logo_formato_invalido(
    client, auth_headers, tmp_path, monkeypatch
):
    import app.services.configuracao_service as configuracao_service

    monkeypatch.setattr(
        configuracao_service, "DIRETORIO_UPLOADS", str(tmp_path)
    )

    response = client.post(
        "/configuracoes/logo",
        files={"arquivo": ("logo.gif", b"conteudo", "image/gif")},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_upload_logo_exige_admin(client, auth_headers_comum):
    response = client.post(
        "/configuracoes/logo",
        files={"arquivo": ("logo.png", b"conteudo", "image/png")},
        headers=auth_headers_comum,
    )

    assert response.status_code == 403


def test_buscar_logo_sem_logo_cadastrada(client, auth_headers):
    response = client.get("/configuracoes/logo", headers=auth_headers)

    assert response.status_code == 400
