def test_criar_produto(client, auth_headers):
    response = client.post(
        "/produtos/",
        json={
            "codigo": "P100",
            "nome": "Arroz 5kg",
            "categoria": "Mercearia",
            "preco_custo": "15.00",
            "preco_venda": "22.90",
            "estoque": 30,
            "estoque_minimo": 5,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    assert response.json()["codigo"] == "P100"


def test_listar_produtos(client, auth_headers, produto):
    response = client.get("/produtos/", headers=auth_headers)

    assert response.status_code == 200

    codigos = [p["codigo"] for p in response.json()]

    assert produto.codigo in codigos


def test_buscar_produto_inexistente(client, auth_headers):
    response = client.get("/produtos/9999", headers=auth_headers)

    assert response.status_code == 404


def test_atualizar_produto(client, auth_headers, produto):
    response = client.put(
        f"/produtos/{produto.id}",
        json={
            "codigo": produto.codigo,
            "nome": "Nome Atualizado",
            "categoria": produto.categoria,
            "preco_custo": str(produto.preco_custo),
            "preco_venda": str(produto.preco_venda),
            "estoque": produto.estoque,
            "estoque_minimo": produto.estoque_minimo,
            "ativo": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["nome"] == "Nome Atualizado"


def test_atualizar_produto_inexistente(client, auth_headers):
    response = client.put(
        "/produtos/9999",
        json={
            "codigo": "X",
            "nome": "X",
            "preco_custo": "1.00",
            "preco_venda": "2.00",
            "estoque": 0,
            "estoque_minimo": 0,
            "ativo": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_excluir_produto(client, auth_headers, produto):
    # Exclusão é soft-delete (ativo=False) -- um produto já vendido tem
    # itens_venda apontando pra ele, então apagar de vez quebraria a
    # integridade referencial (ver ProdutoService.excluir). O registro
    # continua existindo e buscável por id, só marcado como inativo.
    response = client.delete(f"/produtos/{produto.id}", headers=auth_headers)

    assert response.status_code == 200

    depois = client.get(f"/produtos/{produto.id}", headers=auth_headers)

    assert depois.status_code == 200
    assert depois.json()["ativo"] is False


def test_estoque_minimo_e_por_loja_com_fallback_pro_global(
    client, auth_headers, produto, db
):
    """Onda 1 da Fase 2: editar 'estoque mínimo' com loja_id resolvido
    grava em EstoqueLoja.estoque_minimo daquela loja, não no
    Produto.estoque_minimo global -- outra loja que nunca configurou o
    dela continua vendo o mínimo global como fallback."""
    from app.models.loja import Loja

    loja_a = Loja(nome="Loja Estoque A")
    loja_b = Loja(nome="Loja Estoque B")
    db.add_all([loja_a, loja_b])
    db.commit()

    minimo_global_original = produto.estoque_minimo

    response = client.put(
        f"/produtos/{produto.id}?loja_id={loja_a.id}",
        json={
            "codigo": produto.codigo,
            "nome": produto.nome,
            "categoria": produto.categoria,
            "preco_custo": str(produto.preco_custo),
            "preco_venda": str(produto.preco_venda),
            "estoque_minimo": minimo_global_original + 50,
            "ativo": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["estoque_minimo"] == minimo_global_original + 50

    # Loja B nunca configurou o próprio mínimo -- deve continuar vendo
    # o global (inalterado pela edição da Loja A).
    resposta_loja_b = client.get(
        f"/produtos/{produto.id}?loja_id={loja_b.id}", headers=auth_headers
    )
    assert resposta_loja_b.json()["estoque_minimo"] == minimo_global_original

    # Sem loja_id (visão agregada/admin) o global também não deve ter
    # sido sobrescrito pela edição feita na Loja A.
    resposta_global = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    )
    assert resposta_global.json()["estoque_minimo"] == minimo_global_original
