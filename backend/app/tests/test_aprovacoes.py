def test_listar_pendentes_so_admin(client, auth_headers, auth_headers_comum, cliente):

    client.delete(f"/clientes/{cliente.id}", headers=auth_headers_comum)

    response_comum = client.get("/aprovacoes/pendentes", headers=auth_headers_comum)
    assert response_comum.status_code == 403

    response_admin = client.get("/aprovacoes/pendentes", headers=auth_headers)
    assert response_admin.status_code == 200

    pendentes = response_admin.json()
    assert len(pendentes) == 1
    assert pendentes[0]["tipo"] == "EXCLUIR_CLIENTE"
    assert pendentes[0]["referencia_id"] == cliente.id
    assert pendentes[0]["status"] == "PENDENTE"


def test_aprovar_exclusao_de_cliente_executa_a_acao(
    client, auth_headers, auth_headers_comum, cliente
):

    client.delete(f"/clientes/{cliente.id}", headers=auth_headers_comum)

    solicitacao_id = client.get(
        "/aprovacoes/pendentes", headers=auth_headers
    ).json()[0]["id"]

    response = client.post(
        f"/aprovacoes/{solicitacao_id}/aprovar", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "APROVADA"
    assert response.json()["aprovador_id"] is not None
    assert response.json()["resolvido_em"] is not None

    # a acao de verdade rodou -- cliente foi mesmo desativado
    cliente_response = client.get(f"/clientes/{cliente.id}", headers=auth_headers)
    assert cliente_response.json()["ativo"] is False

    # nao aparece mais como pendente
    pendentes = client.get("/aprovacoes/pendentes", headers=auth_headers).json()
    assert pendentes == []


def test_rejeitar_exclusao_de_cliente_nao_executa_a_acao(
    client, auth_headers, auth_headers_comum, cliente
):

    client.delete(f"/clientes/{cliente.id}", headers=auth_headers_comum)

    solicitacao_id = client.get(
        "/aprovacoes/pendentes", headers=auth_headers
    ).json()[0]["id"]

    response = client.post(
        f"/aprovacoes/{solicitacao_id}/rejeitar", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "REJEITADA"

    # cliente continua ativo -- a rejeicao nao executa a acao
    cliente_response = client.get(f"/clientes/{cliente.id}", headers=auth_headers)
    assert cliente_response.json()["ativo"] is True


def test_usuario_comum_nao_pode_aprovar_nem_rejeitar(
    client, auth_headers, auth_headers_comum, cliente
):

    client.delete(f"/clientes/{cliente.id}", headers=auth_headers_comum)

    solicitacao_id = client.get(
        "/aprovacoes/pendentes", headers=auth_headers
    ).json()[0]["id"]

    aprovar = client.post(
        f"/aprovacoes/{solicitacao_id}/aprovar", headers=auth_headers_comum
    )
    assert aprovar.status_code == 403

    rejeitar = client.post(
        f"/aprovacoes/{solicitacao_id}/rejeitar", headers=auth_headers_comum
    )
    assert rejeitar.status_code == 403


def test_aprovar_solicitacao_ja_resolvida_da_erro(
    client, auth_headers, auth_headers_comum, cliente
):

    client.delete(f"/clientes/{cliente.id}", headers=auth_headers_comum)

    solicitacao_id = client.get(
        "/aprovacoes/pendentes", headers=auth_headers
    ).json()[0]["id"]

    client.post(f"/aprovacoes/{solicitacao_id}/aprovar", headers=auth_headers)

    resposta_dupla = client.post(
        f"/aprovacoes/{solicitacao_id}/aprovar", headers=auth_headers
    )

    assert resposta_dupla.status_code == 400


def test_aprovar_solicitacao_inexistente_da_erro(client, auth_headers):

    response = client.post("/aprovacoes/999999/aprovar", headers=auth_headers)

    assert response.status_code == 400
