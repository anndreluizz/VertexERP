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


def test_login_bloqueia_apos_muitas_senhas_erradas(client, usuario):

    from app.auth.rate_limit import MAX_TENTATIVAS

    for _ in range(MAX_TENTATIVAS):
        response = client.post(
            "/auth/login",
            json={"email": usuario.email, "senha": "senha-errada"},
        )
        assert response.status_code == 401

    # a tentativa seguinte (mesmo com a senha CERTA) e barrada antes
    # de sequer checar a senha -- e o ponto do rate limit, nao deixar
    # continuar adivinhando pra sempre
    bloqueada = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "123456"},
    )

    assert bloqueada.status_code == 429
    assert "Tente novamente" in bloqueada.json()["detail"]


def test_login_email_inexistente_tambem_conta_pro_bloqueio(client):

    from app.auth.rate_limit import MAX_TENTATIVAS

    email = "naoexiste@vertex.com"

    for _ in range(MAX_TENTATIVAS):
        response = client.post(
            "/auth/login", json={"email": email, "senha": "qualquer"}
        )
        assert response.status_code == 401

    bloqueada = client.post(
        "/auth/login", json={"email": email, "senha": "qualquer"}
    )

    assert bloqueada.status_code == 429


def test_login_com_sucesso_antes_do_limite_nao_bloqueia(client, usuario):

    from app.auth.rate_limit import MAX_TENTATIVAS

    for _ in range(MAX_TENTATIVAS - 1):
        client.post(
            "/auth/login",
            json={"email": usuario.email, "senha": "senha-errada"},
        )

    # loga certo antes de bater o limite -- reseta o contador
    sucesso = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "123456"},
    )
    assert sucesso.status_code == 200

    # confirma que o contador zerou: da pra errar de novo sem ser
    # bloqueado na hora
    proxima = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "senha-errada"},
    )
    assert proxima.status_code == 401
