def test_usuario_comum_nao_pode_excluir_cliente(
    client, auth_headers_comum, cliente
):
    # Excluir cliente não é um bloqueio seco (403) -- usuário comum só
    # consegue pedir, um admin precisa aprovar depois (ver
    # AprovacaoService / api/v1/clientes.py::excluir_cliente).
    response = client.delete(
        f"/clientes/{cliente.id}", headers=auth_headers_comum
    )

    assert response.status_code == 200
    assert response.json()["aprovacao_pendente"] is True


def test_usuario_comum_nao_pode_excluir_categoria(
    client, auth_headers, auth_headers_comum
):
    criada = client.post(
        "/categorias/",
        json={"nome": "Bebidas"},
        headers=auth_headers,
    ).json()

    response = client.delete(
        f"/categorias/{criada['id']}", headers=auth_headers_comum
    )

    assert response.status_code == 403


def test_usuario_comum_nao_pode_excluir_produto(
    client, auth_headers_comum, produto
):
    response = client.delete(
        f"/produtos/{produto.id}", headers=auth_headers_comum
    )

    assert response.status_code == 403


def test_usuario_comum_nao_pode_excluir_venda(
    client, auth_headers, auth_headers_comum, produto, caixa_aberto
):
    criada = client.post(
        "/vendas/",
        json={
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": 1,
                    "valor_unitario": "10.00",
                }
            ],
        },
        headers=auth_headers,
    ).json()

    response = client.delete(
        f"/vendas/{criada['id']}", headers=auth_headers_comum
    )

    assert response.status_code == 403


def test_usuario_comum_nao_pode_fechar_caixa(
    client, auth_headers_comum, caixa_aberto
):
    response = client.post("/caixa/fechar", headers=auth_headers_comum)

    assert response.status_code == 403


def test_usuario_comum_nao_pode_cancelar_conta_pagar(
    client, auth_headers, auth_headers_comum
):
    # Conta PENDENTE (nenhum dinheiro saiu ainda) é baixo risco -- pode
    # ser cancelada direto por qualquer usuário autenticado (ver
    # docstring de api/v1/contas_pagar.py::cancelar). O bloqueio de
    # verdade pra usuário comum é numa conta JÁ PAGA: aí ele só
    # consegue pedir aprovação, não cancela na hora.
    conta = client.post(
        "/contas-pagar/",
        json={
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": "100.00",
        },
        headers=auth_headers,
    ).json()

    client.post(f"/contas-pagar/{conta['id']}/pagar", headers=auth_headers)

    response = client.post(
        f"/contas-pagar/{conta['id']}/cancelar",
        headers=auth_headers_comum,
    )

    assert response.status_code == 200
    assert response.json()["aprovacao_pendente"] is True

    # a conta continua PAGA -- usuário comum só pediu, não cancelou
    pagas = client.get("/contas-pagar/pagas", headers=auth_headers).json()

    assert any(c["id"] == conta["id"] for c in pagas)


def test_usuario_comum_nao_pode_cancelar_conta_receber(
    client, auth_headers, auth_headers_comum, cliente
):
    conta = client.post(
        "/contas-receber/",
        json={
            "cliente_id": cliente.id,
            "data_vencimento": "2026-12-31T00:00:00",
            "valor": 100.0,
        },
        headers=auth_headers,
    ).json()

    response = client.post(
        f"/contas-receber/{conta['id']}/cancelar",
        headers=auth_headers_comum,
    )

    assert response.status_code == 403


def test_admin_pode_excluir_cliente(client, auth_headers, cliente):
    response = client.delete(f"/clientes/{cliente.id}", headers=auth_headers)

    assert response.status_code == 200


def test_usuario_comum_nao_pode_promover_outro_usuario(
    client, auth_headers_comum, usuario
):
    response = client.put(
        f"/users/{usuario.id}",
        json={"admin": True},
        headers=auth_headers_comum,
    )

    assert response.status_code == 403


def test_admin_pode_promover_usuario_a_admin(
    client, auth_headers, usuario_comum, cliente
):
    response = client.put(
        f"/users/{usuario_comum.id}",
        json={"admin": True},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["admin"] is True

    # loga de novo pra pegar um token que reflita a promoção
    novo_token = client.post(
        "/auth/login",
        json={"email": usuario_comum.email, "senha": "123456"},
    ).json()["access_token"]

    novos_headers = {"Authorization": f"Bearer {novo_token}"}

    # exclusao de cliente e bloqueada (403) pra usuario comum -- prova
    # de que o token novo ja reflete o poder de admin
    resposta_exclusao = client.delete(
        f"/clientes/{cliente.id}", headers=novos_headers
    )

    assert resposta_exclusao.status_code == 200
