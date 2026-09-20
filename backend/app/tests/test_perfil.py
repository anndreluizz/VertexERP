def test_criar_perfil(client, auth_headers):
    response = client.post(
        "/perfis/",
        json={"nome": "Gerente", "permissoes": ["produtos.excluir", "caixa.fechar"]},
        headers=auth_headers,
    )

    assert response.status_code == 200
    dados = response.json()
    assert dados["nome"] == "Gerente"
    assert set(dados["permissoes"]) == {"produtos.excluir", "caixa.fechar"}


def test_criar_perfil_com_permissao_invalida_falha(client, auth_headers):
    response = client.post(
        "/perfis/",
        json={"nome": "Inválido", "permissoes": ["produtos.voar"]},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_criar_perfil_duplicado_falha(client, auth_headers):
    client.post(
        "/perfis/", json={"nome": "Supervisor", "permissoes": []},
        headers=auth_headers,
    )
    response = client.post(
        "/perfis/", json={"nome": "Supervisor", "permissoes": []},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_listar_perfis(client, auth_headers):
    client.post(
        "/perfis/", json={"nome": "Vendedor", "permissoes": []},
        headers=auth_headers,
    )

    response = client.get("/perfis/", headers=auth_headers)

    assert response.status_code == 200
    assert "Vendedor" in [p["nome"] for p in response.json()]


def test_atualizar_perfil(client, auth_headers):
    criado = client.post(
        "/perfis/", json={"nome": "Caixa", "permissoes": []},
        headers=auth_headers,
    ).json()

    response = client.put(
        f"/perfis/{criado['id']}",
        json={"nome": "Caixa", "permissoes": ["caixa.fechar"]},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["permissoes"] == ["caixa.fechar"]


def test_excluir_perfil_em_uso_falha(client, auth_headers, usuario_comum, db):
    perfil = client.post(
        "/perfis/", json={"nome": "Em Uso", "permissoes": []},
        headers=auth_headers,
    ).json()

    usuario_comum.perfil_id = perfil["id"]
    db.commit()

    response = client.delete(f"/perfis/{perfil['id']}", headers=auth_headers)

    assert response.status_code == 400


def test_excluir_perfil(client, auth_headers):
    perfil = client.post(
        "/perfis/", json={"nome": "Descartável", "permissoes": []},
        headers=auth_headers,
    ).json()

    response = client.delete(f"/perfis/{perfil['id']}", headers=auth_headers)

    assert response.status_code == 200


def test_usuario_comum_sem_permissao_nao_pode_excluir_produto(
    client, auth_headers_comum, produto
):
    response = client.delete(
        f"/produtos/{produto.id}", headers=auth_headers_comum
    )

    assert response.status_code == 403


def test_usuario_comum_com_perfil_pode_excluir_produto(
    client, auth_headers, auth_headers_comum, usuario_comum, produto, db
):
    perfil = client.post(
        "/perfis/",
        json={"nome": "Pode Excluir Produto", "permissoes": ["produtos.excluir"]},
        headers=auth_headers,
    ).json()

    usuario_comum.perfil_id = perfil["id"]
    db.commit()

    response = client.delete(
        f"/produtos/{produto.id}", headers=auth_headers_comum
    )

    assert response.status_code == 200


def test_usuario_comum_com_perfil_sem_a_permissao_continua_bloqueado(
    client, auth_headers, auth_headers_comum, usuario_comum, produto, db
):
    perfil = client.post(
        "/perfis/",
        json={"nome": "So Caixa", "permissoes": ["caixa.fechar"]},
        headers=auth_headers,
    ).json()

    usuario_comum.perfil_id = perfil["id"]
    db.commit()

    response = client.delete(
        f"/produtos/{produto.id}", headers=auth_headers_comum
    )

    assert response.status_code == 403


def test_admin_sempre_passa_mesmo_sem_perfil(client, auth_headers, produto):
    response = client.delete(
        f"/produtos/{produto.id}", headers=auth_headers
    )

    assert response.status_code == 200


def test_me_retorna_permissoes_do_perfil(
    client, auth_headers, auth_headers_comum, usuario_comum, db
):
    perfil = client.post(
        "/perfis/",
        json={"nome": "Com Permissoes", "permissoes": ["vendas.cancelar"]},
        headers=auth_headers,
    ).json()

    usuario_comum.perfil_id = perfil["id"]
    db.commit()

    response = client.get("/auth/me", headers=auth_headers_comum)

    assert response.status_code == 200
    dados = response.json()
    assert dados["perfil_nome"] == "Com Permissoes"
    assert dados["permissoes"] == ["vendas.cancelar"]


def test_me_admin_ve_catalogo_inteiro_de_permissoes(client, auth_headers):
    response = client.get("/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert len(response.json()["permissoes"]) > 0


def test_atualizar_usuario_com_perfil_inexistente_falha(
    client, auth_headers, usuario_comum
):
    response = client.put(
        f"/users/{usuario_comum.id}",
        json={"perfil_id": 999999},
        headers=auth_headers,
    )

    assert response.status_code == 400
