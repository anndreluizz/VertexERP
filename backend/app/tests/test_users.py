def test_criar_usuario(client, auth_headers):
    response = client.post(
        "/users/",
        json={
            "nome": "Novo Usuário",
            "email": "novo@vertex.com",
            "senha": "123456",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    dados = response.json()["data"]

    assert dados["email"] == "novo@vertex.com"
    assert dados["ativo"] is True
    assert dados["admin"] is False
    assert "senha" not in dados


def test_criar_usuario_com_email_duplicado(client, auth_headers, usuario):
    response = client.post(
        "/users/",
        json={
            "nome": "Outro Usuário",
            "email": usuario.email,
            "senha": "outra-senha",
        },
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "E-mail já cadastrado."


def test_criar_usuario_sem_login_e_negado(client, usuario):
    # Sem NENHUM usuário cadastrado ainda, o cadastro fica aberto sem
    # login (bootstrap do primeiro acesso -- ver
    # exigir_admin_apos_primeiro_usuario). Por isso esse teste depende
    # da fixture `usuario`: só a partir do segundo usuário em diante
    # que o cadastro sem login volta a ser negado.
    response = client.post(
        "/users/",
        json={
            "nome": "Sem Login",
            "email": "semlogin@vertex.com",
            "senha": "123456",
        },
    )

    assert response.status_code in (401, 403)


def test_criar_usuario_operador_comum_e_negado(client, auth_headers_comum):
    response = client.post(
        "/users/",
        json={
            "nome": "Tentativa Operador",
            "email": "operador-tenta@vertex.com",
            "senha": "123456",
        },
        headers=auth_headers_comum,
    )

    assert response.status_code == 403


def test_definir_ativo_desativa_usuario(client, auth_headers):
    criado = client.post(
        "/users/",
        json={
            "nome": "Vai Ser Desativado",
            "email": "desativar@vertex.com",
            "senha": "123456",
        },
        headers=auth_headers,
    ).json()["data"]

    response = client.put(
        f"/users/{criado['id']}",
        json={"ativo": False},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["ativo"] is False


def test_definir_ativo_exige_admin(client, auth_headers_comum, usuario):
    response = client.put(
        f"/users/{usuario.id}",
        json={"ativo": False},
        headers=auth_headers_comum,
    )

    assert response.status_code == 403


def test_listar_usuarios(client, auth_headers, usuario):
    response = client.get("/users/", headers=auth_headers)

    assert response.status_code == 200

    emails = [u["email"] for u in response.json()["data"]]

    assert usuario.email in emails


def test_meu_perfil_admin(client, auth_headers, usuario):
    # "Meu perfil" é servido por /auth/me (não tem /users/me) e devolve
    # o UserResponse direto, sem o wrapper {data: ...} do ApiResponse.
    response = client.get("/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["admin"] is True


def test_meu_perfil_usuario_comum(client, auth_headers_comum, usuario_comum):
    response = client.get("/auth/me", headers=auth_headers_comum)

    assert response.status_code == 200
    assert response.json()["admin"] is False


def test_unico_admin_nao_pode_se_autodemover(client, auth_headers, usuario):
    # sem isso, um clique acidental em "Remover da administração" na
    # propria conta trava o sistema inteiro: nenhuma acao que exige
    # admin (aprovar solicitacao, cadastrar usuario, cancelar venda,
    # redefinir senha de outro...) consegue mais ser feita por
    # ninguem, nem reverter essa mesma mudanca
    response = client.put(
        f"/users/{usuario.id}",
        json={"admin": False},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert "único administrador" in response.json()["detail"]


def test_admin_pode_demover_a_si_mesmo_se_houver_outro_admin(
    client, auth_headers, usuario, db
):
    from app.auth.hash import gerar_hash
    from app.models.user import User

    outro_admin = User(
        nome="Outro Admin",
        email="outroadmin@vertex.com",
        senha=gerar_hash("123456"),
        ativo=True,
        admin=True,
    )
    db.add(outro_admin)
    db.commit()

    response = client.put(
        f"/users/{usuario.id}",
        json={"admin": False},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["admin"] is False


def test_admin_pode_desativar_outro_admin_se_permanecer_admin(
    client, auth_headers, usuario, db
):
    from app.auth.hash import gerar_hash
    from app.models.user import User

    outro_admin = User(
        nome="Outro Admin",
        email="outroadmin2@vertex.com",
        senha=gerar_hash("123456"),
        ativo=True,
        admin=True,
    )
    db.add(outro_admin)
    db.commit()
    db.refresh(outro_admin)

    response = client.put(
        f"/users/{outro_admin.id}",
        json={"ativo": False},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["ativo"] is False
