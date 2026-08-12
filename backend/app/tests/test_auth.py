def test_login_com_sucesso(client, usuario):
    response = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "123456"},
    )

    assert response.status_code == 200

    dados = response.json()

    assert "access_token" in dados
    assert dados["token_type"] == "bearer"


def test_login_com_senha_invalida(client, usuario):
    response = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "senha-errada"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Senha inválida."


def test_login_com_email_inexistente(client):
    response = client.post(
        "/auth/login",
        json={"email": "naoexiste@vertex.com", "senha": "123456"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Usuário inválido."


def test_rota_protegida_sem_token(client):
    response = client.get("/categorias/")

    assert response.status_code in (401, 403)
