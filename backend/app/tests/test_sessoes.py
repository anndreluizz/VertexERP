from datetime import datetime, timedelta

from app.models.refresh_token import RefreshToken


def test_login_devolve_refresh_token(client, usuario):
    response = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "123456"},
    )

    assert response.status_code == 200

    dados = response.json()

    assert "refresh_token" in dados
    assert dados["refresh_token"]


def test_refresh_com_token_valido_gera_novo_access_token(client, usuario):
    login = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "123456"},
    ).json()

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    )

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_refresh_com_token_invalido_falha(client):
    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "token-que-nao-existe"},
    )

    assert response.status_code == 401


def test_refresh_com_token_expirado_falha(client, usuario, db):
    login = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "123456"},
    ).json()

    sessao = (
        db.query(RefreshToken)
        .filter(RefreshToken.token == login["refresh_token"])
        .first()
    )
    sessao.expira_em = datetime.utcnow() - timedelta(days=1)
    db.commit()

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    )

    assert response.status_code == 401


def test_refresh_com_token_revogado_falha(client, usuario, auth_headers, db):
    login = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "123456"},
    ).json()

    sessao = (
        db.query(RefreshToken)
        .filter(RefreshToken.token == login["refresh_token"])
        .first()
    )

    client.delete(f"/auth/sessoes/{sessao.id}", headers=auth_headers)

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    )

    assert response.status_code == 401


def test_listar_sessoes_so_mostra_as_proprias(
    client, usuario, usuario_comum, auth_headers, db
):
    sessao_do_outro = RefreshToken(
        usuario_id=usuario_comum.id,
        token="token-de-outro-usuario-listagem",
        expira_em=datetime.utcnow() + timedelta(days=90),
    )
    db.add(sessao_do_outro)
    db.commit()
    db.refresh(sessao_do_outro)

    sessoes = client.get("/auth/sessoes", headers=auth_headers).json()

    ids = [s["id"] for s in sessoes]
    assert sessao_do_outro.id not in ids


def test_listar_sessoes_nao_mostra_expirada(client, usuario, auth_headers, db):
    antes = client.get("/auth/sessoes", headers=auth_headers).json()
    qtd_antes = len(antes)

    sessao = (
        db.query(RefreshToken)
        .filter(RefreshToken.usuario_id == usuario.id)
        .order_by(RefreshToken.id.desc())
        .first()
    )
    sessao.expira_em = datetime.utcnow() - timedelta(days=1)
    db.commit()

    depois = client.get("/auth/sessoes", headers=auth_headers).json()

    assert len(depois) == qtd_antes - 1


def test_revogar_sessao_de_outro_usuario_falha(
    client, usuario, usuario_comum, auth_headers, db
):
    # cria uma sessao pro usuario_comum direto pelo banco (nao pelo
    # login dele, que geraria um token novo sem eu saber o id)
    sessao_do_outro = RefreshToken(
        usuario_id=usuario_comum.id,
        token="token-do-outro-usuario",
        expira_em=datetime.utcnow() + timedelta(days=90),
    )
    db.add(sessao_do_outro)
    db.commit()
    db.refresh(sessao_do_outro)

    # auth_headers e' do usuario (admin) tentando revogar a sessao do
    # usuario_comum -- precisa falhar, mesma checagem de posse ja
    # usada em outras entidades do sistema
    response = client.delete(
        f"/auth/sessoes/{sessao_do_outro.id}", headers=auth_headers
    )

    assert response.status_code == 404

    db.refresh(sessao_do_outro)
    assert sessao_do_outro.revogado is False
