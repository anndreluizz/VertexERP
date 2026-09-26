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
    assert response.json()["detail"] == "E-mail ou senha inválidos."


def test_login_com_email_inexistente(client):
    response = client.post(
        "/auth/login",
        json={"email": "naoexiste@vertex.com", "senha": "123456"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "E-mail ou senha inválidos."


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


def test_login_sem_2fa_ativo_continua_igual(client, usuario):
    """dois_fatores_ativo comeca False no fixture -- confirma que o
    fluxo antigo (token direto) continua intacto pra quem nao ligou
    o 2FA."""

    response = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "123456"},
    )

    assert response.status_code == 200
    dados = response.json()
    assert "access_token" in dados
    assert "requer_2fa" not in dados


def test_login_com_2fa_ativo_nao_devolve_token_ainda(client, db, usuario, monkeypatch):

    usuario.dois_fatores_ativo = True
    db.commit()

    codigos_enviados = []

    def _enviar_falso(db_arg, destinatario, assunto, corpo, **kwargs):
        codigos_enviados.append((destinatario, corpo))
        return True, None

    monkeypatch.setattr(
        "app.api.v1.auth.EmailService.enviar_email", _enviar_falso
    )

    response = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "123456"},
    )

    assert response.status_code == 200
    dados = response.json()

    assert dados["requer_2fa"] is True
    assert "verificacao_id" in dados
    assert "access_token" not in dados

    assert len(codigos_enviados) == 1
    assert codigos_enviados[0][0] == usuario.email


def test_fluxo_completo_de_2fa_ate_o_token(client, db, usuario, monkeypatch):

    usuario.dois_fatores_ativo = True
    db.commit()

    codigo_capturado = {}

    def _capturar_codigo(db_arg, destinatario, assunto, corpo, **kwargs):
        # extrai o codigo de 6 digitos do corpo do e-mail pra usar no
        # segundo passo, sem precisar reimplementar a geracao aqui
        import re
        codigo_capturado["codigo"] = re.search(r"\d{6}", corpo).group()
        return True, None

    monkeypatch.setattr(
        "app.api.v1.auth.EmailService.enviar_email", _capturar_codigo
    )

    primeiro_passo = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "123456"},
    )
    verificacao_id = primeiro_passo.json()["verificacao_id"]

    segundo_passo = client.post(
        "/auth/verificar-2fa",
        json={
            "verificacao_id": verificacao_id,
            "codigo": codigo_capturado["codigo"],
        },
    )

    assert segundo_passo.status_code == 200
    dados = segundo_passo.json()
    assert "access_token" in dados
    assert "refresh_token" in dados
    assert dados["token_type"] == "bearer"


def test_verificar_2fa_com_codigo_errado_falha(client, db, usuario, monkeypatch):

    usuario.dois_fatores_ativo = True
    db.commit()

    monkeypatch.setattr(
        "app.api.v1.auth.EmailService.enviar_email",
        lambda *a, **k: (True, None),
    )

    primeiro_passo = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "123456"},
    )
    verificacao_id = primeiro_passo.json()["verificacao_id"]

    resposta = client.post(
        "/auth/verificar-2fa",
        json={"verificacao_id": verificacao_id, "codigo": "000000"},
    )

    assert resposta.status_code == 401


def test_verificar_2fa_com_verificacao_id_invalido_falha(client):

    resposta = client.post(
        "/auth/verificar-2fa",
        json={"verificacao_id": "nao-existe", "codigo": "123456"},
    )

    assert resposta.status_code == 401


def test_login_com_2fa_falha_de_envio_nao_deixa_passar(client, db, usuario, monkeypatch):
    """Falha fechada: se o e-mail do codigo nao sai (SMTP desligado,
    credencial errada etc.), o login NAO deve simplesmente pular o
    2FA e deixar entrar mesmo assim."""

    usuario.dois_fatores_ativo = True
    db.commit()

    monkeypatch.setattr(
        "app.api.v1.auth.EmailService.enviar_email",
        lambda *a, **k: (False, "SMTP não configurado."),
    )

    resposta = client.post(
        "/auth/login",
        json={"email": usuario.email, "senha": "123456"},
    )

    assert resposta.status_code == 503
    assert "access_token" not in resposta.json()


def test_secret_key_do_jwt_nunca_e_o_literal_publico():
    # o literal antigo esta no GitHub -- se voltar a ser usado, qualquer
    # um forja token de admin em qualquer instalacao
    from app.auth import jwt

    assert jwt.SECRET_KEY
    assert jwt.SECRET_KEY != "VERTEXERP2026SECRET"
