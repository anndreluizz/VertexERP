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


def test_enviar_para_usuario_persiste_notificacao(db, usuario):
    from app.services.notificacao_service import NotificacaoService

    NotificacaoService.enviar_para_usuario(
        db, usuario.id, "Título", "Corpo da notificação"
    )

    from app.models.notificacao import Notificacao

    notificacao = (
        db.query(Notificacao).filter(Notificacao.usuario_id == usuario.id).first()
    )
    assert notificacao is not None
    assert notificacao.titulo == "Título"
    assert notificacao.lida is False


def test_enviar_para_admins_faz_fanout_e_respeita_exclusao(
    db, usuario, usuario_comum
):
    from app.services.notificacao_service import NotificacaoService
    from app.models.notificacao import Notificacao

    # usuario_comum nao e' admin -- so' usuario (admin) deve receber
    NotificacaoService.enviar_para_admins(db, "Aviso", "Corpo")

    assert (
        db.query(Notificacao).filter(Notificacao.usuario_id == usuario.id).count()
        == 1
    )
    assert (
        db.query(Notificacao)
        .filter(Notificacao.usuario_id == usuario_comum.id)
        .count()
        == 0
    )


def test_listar_notificacoes_mostra_so_as_do_usuario_logado(
    client, auth_headers, auth_headers_comum, usuario, usuario_comum, db
):
    from app.services.notificacao_service import NotificacaoService

    NotificacaoService.enviar_para_usuario(db, usuario.id, "Pra admin", "x")
    NotificacaoService.enviar_para_usuario(db, usuario_comum.id, "Pra comum", "x")

    response = client.get("/notificacoes/", headers=auth_headers)

    assert response.status_code == 200
    titulos = [n["titulo"] for n in response.json()]
    assert titulos == ["Pra admin"]


def test_contagem_nao_lidas(client, auth_headers, usuario, db):
    from app.services.notificacao_service import NotificacaoService

    NotificacaoService.enviar_para_usuario(db, usuario.id, "A", "x")
    NotificacaoService.enviar_para_usuario(db, usuario.id, "B", "x")

    response = client.get("/notificacoes/nao-lidas", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["nao_lidas"] == 2


def test_marcar_lida_atualiza_so_a_notificacao_certa(
    client, auth_headers, usuario, db
):
    from app.services.notificacao_service import NotificacaoService
    from app.models.notificacao import Notificacao

    NotificacaoService.enviar_para_usuario(db, usuario.id, "A", "x")
    NotificacaoService.enviar_para_usuario(db, usuario.id, "B", "x")

    notificacoes = (
        db.query(Notificacao).filter(Notificacao.usuario_id == usuario.id).all()
    )
    alvo = notificacoes[0]

    response = client.post(
        f"/notificacoes/{alvo.id}/marcar-lida", headers=auth_headers
    )

    assert response.status_code == 200

    db.refresh(alvo)
    assert alvo.lida is True

    outra = notificacoes[1]
    db.refresh(outra)
    assert outra.lida is False


def test_marcar_lida_de_notificacao_de_outro_usuario_da_404(
    client, auth_headers, auth_headers_comum, usuario_comum, db
):
    from app.services.notificacao_service import NotificacaoService
    from app.models.notificacao import Notificacao

    NotificacaoService.enviar_para_usuario(db, usuario_comum.id, "Da comum", "x")

    notificacao = (
        db.query(Notificacao)
        .filter(Notificacao.usuario_id == usuario_comum.id)
        .first()
    )

    response = client.post(
        f"/notificacoes/{notificacao.id}/marcar-lida", headers=auth_headers
    )

    assert response.status_code == 404


def test_marcar_todas_lidas(client, auth_headers, usuario, db):
    from app.services.notificacao_service import NotificacaoService

    NotificacaoService.enviar_para_usuario(db, usuario.id, "A", "x")
    NotificacaoService.enviar_para_usuario(db, usuario.id, "B", "x")

    response = client.post("/notificacoes/marcar-todas-lidas", headers=auth_headers)

    assert response.status_code == 200

    contagem = client.get("/notificacoes/nao-lidas", headers=auth_headers)
    assert contagem.json()["nao_lidas"] == 0


# ---- avisos de movimento de cliente/venda: vao pra todos os admins,
# inclusive quem fez a acao (dono vende no PDV e quer o registro no
# celular -- antes quem fazia era excluido do aviso)


def _titulos_do(db, usuario_id):
    from app.models.notificacao import Notificacao

    return [
        n.titulo
        for n in db.query(Notificacao)
        .filter(Notificacao.usuario_id == usuario_id)
        .all()
    ]


def _corpo(db, usuario_id, titulo):
    from app.models.notificacao import Notificacao

    return (
        db.query(Notificacao)
        .filter(
            Notificacao.usuario_id == usuario_id,
            Notificacao.titulo == titulo,
        )
        .first()
        .corpo
    )


def _venda_no_fiado(client, auth_headers, produto, cliente, quantidade=5):
    return client.post(
        "/vendas/",
        json={
            "cliente_id": cliente.id,
            "forma_pagamento": "PRAZO",
            "data_vencimento": "2026-12-31T00:00:00",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": quantidade,
                    "valor_unitario": "20.00",
                }
            ],
        },
        headers=auth_headers,
    )


def test_venda_no_fiado_avisa_inclusive_quem_vendeu(
    client, auth_headers, db, usuario, produto, cliente, caixa_aberto
):
    assert _venda_no_fiado(client, auth_headers, produto, cliente).status_code == 201

    assert "Venda no fiado" in _titulos_do(db, usuario.id)
    assert cliente.nome in _corpo(db, usuario.id, "Venda no fiado")


def test_pagamento_de_fiado_avisa_com_saldo_restante(
    client, auth_headers, db, usuario, produto, cliente, caixa_aberto
):
    _venda_no_fiado(client, auth_headers, produto, cliente)  # deve R$ 100

    client.post(
        "/fiado/pagamento",
        json={"cliente_id": cliente.id, "valor": 40.0},
        headers=auth_headers,
    )

    corpo = _corpo(db, usuario.id, "Recebimento de fiado")
    assert "R$ 40,00" in corpo
    assert "Saldo devedor: R$ 60,00" in corpo


def test_haver_avisa(client, auth_headers, db, usuario, produto, cliente, caixa_aberto):
    _venda_no_fiado(client, auth_headers, produto, cliente)

    response = client.post(
        "/fiado/movimentos",
        json={"cliente_id": cliente.id, "tipo": "HAVER", "valor": 10.0},
        headers=auth_headers,
    )
    assert response.status_code == 200

    assert "Haver lançado" in _titulos_do(db, usuario.id)


def test_conta_a_receber_recebida_avisa(
    client, auth_headers, db, usuario, cliente, caixa_aberto
):
    conta = client.post(
        "/contas-receber/",
        json={
            "cliente_id": cliente.id,
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": 200.0,
        },
        headers=auth_headers,
    ).json()

    client.post(f"/contas-receber/{conta['id']}/receber", headers=auth_headers)

    corpo = _corpo(db, usuario.id, "Conta recebida")
    assert cliente.nome in corpo
    assert "R$ 200,00" in corpo
