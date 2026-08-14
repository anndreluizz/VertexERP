from app.models.device_token import DeviceToken


def test_registrar_token(client, auth_headers, usuario, db):
    response = client.post(
        "/notificacoes/registrar-token",
        json={"token": "token-de-teste-abc", "plataforma": "ANDROID"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    registrado = (
        db.query(DeviceToken)
        .filter(DeviceToken.token == "token-de-teste-abc")
        .first()
    )
    assert registrado is not None
    assert registrado.usuario_id == usuario.id


def test_registrar_token_existente_transfere_dono(
    client, auth_headers, auth_headers_comum, usuario_comum, db
):
    # mesmo token de aparelho registrado de novo por outro usuario
    # (ex.: outra pessoa loga no mesmo celular) -- atualiza o dono em
    # vez de duplicar (ver DeviceTokenService.registrar)
    client.post(
        "/notificacoes/registrar-token",
        json={"token": "token-compartilhado", "plataforma": "ANDROID"},
        headers=auth_headers,
    )

    client.post(
        "/notificacoes/registrar-token",
        json={"token": "token-compartilhado", "plataforma": "ANDROID"},
        headers=auth_headers_comum,
    )

    registros = (
        db.query(DeviceToken)
        .filter(DeviceToken.token == "token-compartilhado")
        .all()
    )

    assert len(registros) == 1
    assert registros[0].usuario_id == usuario_comum.id


def test_remover_proprio_token(client, auth_headers, db):
    client.post(
        "/notificacoes/registrar-token",
        json={"token": "token-pra-remover", "plataforma": "ANDROID"},
        headers=auth_headers,
    )

    response = client.delete(
        "/notificacoes/token/token-pra-remover", headers=auth_headers
    )

    assert response.status_code == 200

    assert (
        db.query(DeviceToken)
        .filter(DeviceToken.token == "token-pra-remover")
        .first()
        is None
    )


def test_nao_remove_token_de_outro_usuario(
    client, auth_headers, auth_headers_comum, db
):
    client.post(
        "/notificacoes/registrar-token",
        json={"token": "token-do-admin", "plataforma": "ANDROID"},
        headers=auth_headers,
    )

    # usuario_comum tenta apagar o token que pertence ao admin
    response = client.delete(
        "/notificacoes/token/token-do-admin", headers=auth_headers_comum
    )

    # a rota nao vaza se o token existe ou nao (sempre 200), mas o
    # registro do dono de verdade continua intacto
    assert response.status_code == 200

    assert (
        db.query(DeviceToken)
        .filter(DeviceToken.token == "token-do-admin")
        .first()
        is not None
    )
