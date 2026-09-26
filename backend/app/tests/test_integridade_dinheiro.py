"""Regras que protegem dinheiro/estoque de um operador comum (ou do app
mobile com o token dele): preco e quantidade da venda, e correcao/
perdao de divida no fiado. Admin continua podendo tudo."""

import pytest

from app.models.caixa import Caixa


@pytest.fixture()
def caixa_aberto_comum(db, usuario_comum):
    novo = Caixa(
        saldo_inicial=0,
        saldo_final=0,
        status="ABERTO",
        usuario_id=usuario_comum.id,
    )
    db.add(novo)
    db.commit()
    return novo


def _venda(client, headers, produto, quantidade=1, valor="20.00", **extra):
    return client.post(
        "/vendas/",
        json={
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": produto.id,
                    "quantidade": quantidade,
                    "valor_unitario": valor,
                }
            ],
            **extra,
        },
        headers=headers,
    )


@pytest.mark.parametrize("quantidade", [0, -5])
def test_venda_recusa_quantidade_zero_ou_negativa(
    client, auth_headers, produto, caixa_aberto, quantidade
):
    response = _venda(client, auth_headers, produto, quantidade=quantidade)

    assert response.status_code == 422


def test_operador_nao_vende_com_preco_diferente_do_cadastro(
    client, auth_headers_comum, produto, caixa_aberto_comum
):
    response = _venda(client, auth_headers_comum, produto, valor="1.00")

    assert response.status_code == 400
    assert "preço" in response.json()["detail"]


def test_operador_vende_pelo_preco_do_cadastro(
    client, auth_headers_comum, produto, caixa_aberto_comum
):
    response = _venda(client, auth_headers_comum, produto, valor="20.00")

    assert response.status_code == 201


def _venda_no_fiado(client, auth_headers, produto, cliente):
    response = _venda(
        client,
        auth_headers,
        produto,
        quantidade=5,
        cliente_id=cliente.id,
        forma_pagamento="PRAZO",
        data_vencimento="2026-12-31T00:00:00",
    )
    assert response.status_code == 201

    movimentos = client.get(
        f"/fiado/movimentos/cliente/{cliente.id}", headers=auth_headers
    ).json()

    return movimentos[0]


def test_operador_nao_edita_nem_apaga_fiado(
    client, auth_headers, auth_headers_comum, produto, cliente, caixa_aberto
):
    movimento = client.post(
        "/fiado/compra",
        json={"cliente_id": cliente.id, "valor": 50.0},
        headers=auth_headers,
    ).json()

    editar = client.put(
        f"/fiado/movimentos/{movimento['id']}",
        json={"valor": 0.01},
        headers=auth_headers_comum,
    )
    apagar = client.delete(
        f"/fiado/movimentos/{movimento['id']}", headers=auth_headers_comum
    )

    assert editar.status_code == 403
    assert apagar.status_code == 403


def test_operador_nao_perdoa_divida_sem_dinheiro(
    client, auth_headers, auth_headers_comum, produto, cliente, caixa_aberto
):
    _venda_no_fiado(client, auth_headers, produto, cliente)

    haver = client.post(
        "/fiado/movimentos",
        json={"cliente_id": cliente.id, "tipo": "HAVER", "valor": 100.0},
        headers=auth_headers_comum,
    )
    pagamento_sem_forma = client.post(
        "/fiado/pagamento",
        json={"cliente_id": cliente.id, "valor": 100.0},
        headers=auth_headers_comum,
    )

    assert haver.status_code == 403
    assert pagamento_sem_forma.status_code == 403


def test_lancamento_que_veio_de_venda_nao_e_editado_direto(
    client, auth_headers, produto, cliente, caixa_aberto
):
    movimento = _venda_no_fiado(client, auth_headers, produto, cliente)
    assert movimento["venda_id"] is not None

    editar = client.put(
        f"/fiado/movimentos/{movimento['id']}",
        json={"valor": 1.0},
        headers=auth_headers,
    )
    apagar = client.delete(
        f"/fiado/movimentos/{movimento['id']}", headers=auth_headers
    )

    assert editar.status_code == 400
    assert "cancele a venda" in editar.json()["detail"]
    assert apagar.status_code == 400


def test_correcao_de_fiado_recusa_valor_zero(
    client, auth_headers, cliente, caixa_aberto
):
    movimento = client.post(
        "/fiado/compra",
        json={"cliente_id": cliente.id, "valor": 50.0},
        headers=auth_headers,
    ).json()

    response = client.put(
        f"/fiado/movimentos/{movimento['id']}",
        json={"valor": 0},
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_cancelar_venda_suspensa_nao_devolve_estoque_fantasma(
    client, auth_headers, produto, caixa_aberto
):
    suspensa = client.post(
        "/vendas/suspender",
        json={
            "itens": [
                {"produto_id": produto.id, "quantidade": 3, "valor_unitario": "20.00"}
            ],
        },
        headers=auth_headers,
    ).json()

    estoque_antes = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()["estoque"]

    response = client.delete(f"/vendas/{suspensa['id']}", headers=auth_headers)

    estoque_depois = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()["estoque"]

    assert response.status_code == 400
    assert estoque_depois == estoque_antes


def test_reenvio_com_a_mesma_chave_nao_vende_duas_vezes(
    client, auth_headers, produto, caixa_aberto
):
    # resposta da 1a tentativa "se perdeu" (timeout) e o caixa reenviou
    chave = "carrinho-abc123456"

    primeira = _venda(
        client, auth_headers, produto, quantidade=2, chave_idempotencia=chave
    )
    segunda = _venda(
        client, auth_headers, produto, quantidade=2, chave_idempotencia=chave
    )

    estoque = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()["estoque"]

    assert primeira.status_code == 201
    assert segunda.status_code == 201
    assert segunda.json()["id"] == primeira.json()["id"]
    assert estoque == 50 - 2


def test_vendas_sem_chave_continuam_independentes(
    client, auth_headers, produto, caixa_aberto
):
    a = _venda(client, auth_headers, produto)
    b = _venda(client, auth_headers, produto)

    assert a.json()["id"] != b.json()["id"]


def _payload_produto(produto, **mudancas):
    dados = {
        "codigo": produto.codigo,
        "nome": produto.nome,
        "categoria": produto.categoria,
        "preco_custo": str(produto.preco_custo),
        "preco_venda": str(produto.preco_venda),
        "estoque": produto.estoque,
        "estoque_minimo": produto.estoque_minimo,
        "ativo": True,
    }
    dados.update(mudancas)
    return dados


def test_operador_nao_muda_preco_do_produto(client, auth_headers_comum, produto):
    # sem isso a trava de preco da venda era contornada: baixa o preco,
    # vende, volta o preco
    response = client.put(
        f"/produtos/{produto.id}",
        json=_payload_produto(produto, preco_venda="1.00"),
        headers=auth_headers_comum,
    )

    assert response.status_code == 403


def test_operador_ainda_edita_o_resto_do_produto(
    client, auth_headers_comum, produto
):
    # o formulario manda o preco junto, mas igual ao atual -- nao bloqueia
    response = client.put(
        f"/produtos/{produto.id}",
        json=_payload_produto(produto, nome="Nome Novo"),
        headers=auth_headers_comum,
    )

    assert response.status_code == 200
    assert response.json()["nome"] == "Nome Novo"


def test_operador_nao_ajusta_estoque_na_mao(client, auth_headers_comum, produto):
    response = client.post(
        "/estoque/movimentos",
        json={
            "produto_id": produto.id,
            "tipo": "ENTRADA",
            "quantidade": 100,
            "motivo": "teste",
        },
        headers=auth_headers_comum,
    )

    assert response.status_code == 403


def test_operador_da_filial_nao_registra_na_matriz(
    client, db, usuario_comum, auth_headers_comum
):
    from app.models.loja import Loja

    matriz = Loja(nome="Matriz")
    filial = Loja(nome="Filial")
    db.add_all([matriz, filial])
    db.commit()

    usuario_comum.loja_id = filial.id
    db.commit()

    response = client.post(
        f"/caixa/abrir?loja_id={matriz.id}",
        json={"saldo_inicial": 0},
        headers=auth_headers_comum,
    )

    assert response.status_code == 400
    assert "outra loja" in response.json()["detail"]


def test_filial_so_ve_as_vendas_da_propria_loja(
    client, db, auth_headers, usuario, usuario_comum, auth_headers_comum, produto
):
    # antes, sem ?loja_id= a Filial via o faturamento de todas as lojas
    from app.models.loja import Loja

    matriz = Loja(nome="Matriz")
    filial = Loja(nome="Filial")
    db.add_all([matriz, filial])
    db.commit()

    for loja in (matriz, filial):
        db.add(
            Caixa(
                saldo_inicial=0,
                saldo_final=0,
                status="ABERTO",
                usuario_id=usuario.id,
                loja_id=loja.id,
            )
        )
    db.commit()

    for loja in (matriz, filial):
        # admin registra estoque e uma venda em cada loja
        client.post(
            f"/estoque/movimentos?loja_id={loja.id}",
            json={"produto_id": produto.id, "tipo": "ENTRADA", "quantidade": 5, "motivo": "t"},
            headers=auth_headers,
        )
        resposta = client.post(
            f"/vendas/?loja_id={loja.id}",
            json={
                "forma_pagamento": "DINHEIRO",
                "itens": [{"produto_id": produto.id, "quantidade": 1, "valor_unitario": "20.00"}],
            },
            headers=auth_headers,
        )
        assert resposta.status_code == 201, resposta.json()

    usuario_comum.loja_id = filial.id
    db.commit()

    vistas = client.get("/vendas/", headers=auth_headers_comum).json()
    tentando_matriz = client.get(
        f"/vendas/?loja_id={matriz.id}", headers=auth_headers_comum
    ).json()
    admin_ve = client.get("/vendas/", headers=auth_headers).json()

    assert len(vistas) == 1
    # pedir a Matriz explicitamente nao adianta: continua vendo so' a Filial
    assert [v["id"] for v in tentando_matriz] == [v["id"] for v in vistas]
    assert len(admin_ve) == 2
