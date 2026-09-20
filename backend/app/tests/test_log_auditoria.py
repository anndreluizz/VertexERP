def test_acao_admin_gerada_via_get_current_admin_e_registrada(
    client, auth_headers, usuario
):
    client.get("/users/", headers=auth_headers)

    logs = client.get("/auditoria/", headers=auth_headers).json()

    encontrado = [
        l for l in logs
        if l["usuario_id"] == usuario.id and l["acao"] == "GET /users/"
    ]
    assert len(encontrado) >= 1


def test_acao_via_permissao_e_registrada_com_a_chave(
    client, auth_headers, produto
):
    client.delete(f"/produtos/{produto.id}", headers=auth_headers)

    logs = client.get("/auditoria/", headers=auth_headers).json()

    encontrado = [l for l in logs if l["acao"] == "produtos.excluir"]
    assert len(encontrado) >= 1


def test_acao_negada_nao_e_registrada(
    client, auth_headers, auth_headers_comum, produto
):
    resposta = client.delete(
        f"/produtos/{produto.id}", headers=auth_headers_comum
    )
    assert resposta.status_code == 403

    logs = client.get("/auditoria/", headers=auth_headers).json()

    assert all(l["acao"] != "produtos.excluir" for l in logs)


def test_usuario_comum_com_perfil_gera_log_com_o_proprio_id(
    client, auth_headers, auth_headers_comum, usuario_comum, produto, db
):
    perfil = client.post(
        "/perfis/",
        json={"nome": "Auditado", "permissoes": ["produtos.excluir"]},
        headers=auth_headers,
    ).json()
    usuario_comum.perfil_id = perfil["id"]
    db.commit()

    client.delete(f"/produtos/{produto.id}", headers=auth_headers_comum)

    logs = client.get(
        f"/auditoria/?usuario_id={usuario_comum.id}", headers=auth_headers
    ).json()

    assert any(l["acao"] == "produtos.excluir" for l in logs)


def test_listar_auditoria_requer_admin(client, auth_headers_comum):
    response = client.get("/auditoria/", headers=auth_headers_comum)

    assert response.status_code == 403


def test_filtro_por_acao(client, auth_headers, produto):
    client.delete(f"/produtos/{produto.id}", headers=auth_headers)

    logs = client.get(
        "/auditoria/?acao=produtos.excluir", headers=auth_headers
    ).json()

    assert len(logs) >= 1
    assert all(l["acao"] == "produtos.excluir" for l in logs)
