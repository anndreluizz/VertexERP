def test_criar_variacao_com_produto_pai(client, auth_headers, produto):
    response = client.post(
        "/produtos/",
        json={
            "codigo": "VAR-AZUL-P",
            "nome": f"{produto.nome} Azul P",
            "cor": "Azul",
            "tamanho": "P",
            "produto_pai_id": produto.id,
            "preco_custo": "10.00",
            "preco_venda": "20.00",
            "estoque": 5,
            "estoque_minimo": 0,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    dados = response.json()
    assert dados["produto_pai_id"] == produto.id
    assert dados["cor"] == "Azul"
    assert dados["tamanho"] == "P"


def test_criar_variacao_com_pai_inexistente_falha(client, auth_headers):
    response = client.post(
        "/produtos/",
        json={
            "codigo": "VAR-ORFA",
            "nome": "Variação Órfã",
            "produto_pai_id": 999999,
            "preco_custo": "10.00",
            "preco_venda": "20.00",
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_variacao_de_variacao_falha(client, auth_headers, produto):
    variacao = client.post(
        "/produtos/",
        json={
            "codigo": "VAR-BASE",
            "nome": "Variação Base",
            "produto_pai_id": produto.id,
            "preco_custo": "10.00",
            "preco_venda": "20.00",
        },
        headers=auth_headers,
    ).json()

    response = client.post(
        "/produtos/",
        json={
            "codigo": "VAR-NETA",
            "nome": "Variação Neta",
            "produto_pai_id": variacao["id"],
            "preco_custo": "10.00",
            "preco_venda": "20.00",
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_listar_variacoes(client, auth_headers, produto):
    client.post(
        "/produtos/",
        json={
            "codigo": "VAR-M",
            "nome": f"{produto.nome} M",
            "tamanho": "M",
            "produto_pai_id": produto.id,
            "preco_custo": "10.00",
            "preco_venda": "20.00",
        },
        headers=auth_headers,
    )
    client.post(
        "/produtos/",
        json={
            "codigo": "VAR-G",
            "nome": f"{produto.nome} G",
            "tamanho": "G",
            "produto_pai_id": produto.id,
            "preco_custo": "10.00",
            "preco_venda": "20.00",
        },
        headers=auth_headers,
    )

    response = client.get(
        f"/produtos/{produto.id}/variacoes", headers=auth_headers
    )

    assert response.status_code == 200
    tamanhos = {v["tamanho"] for v in response.json()}
    assert tamanhos == {"M", "G"}


def test_atualizar_para_variacao_de_variacao_falha(
    client, auth_headers, produto, db
):
    from app.models.produto import Produto

    variacao = client.post(
        "/produtos/",
        json={
            "codigo": "VAR-PAI2",
            "nome": "Variação Pai2",
            "produto_pai_id": produto.id,
            "preco_custo": "10.00",
            "preco_venda": "20.00",
        },
        headers=auth_headers,
    ).json()

    outro = Produto(
        codigo="OUTRO-PROD",
        nome="Outro Produto",
        preco_custo=1.0,
        preco_venda=2.0,
        ativo=True,
    )
    db.add(outro)
    db.commit()
    db.refresh(outro)

    response = client.put(
        f"/produtos/{outro.id}",
        json={
            "codigo": outro.codigo,
            "nome": outro.nome,
            "produto_pai_id": variacao["id"],
            "preco_custo": "1.00",
            "preco_venda": "2.00",
            "ativo": True,
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_estoque_e_independente_por_variacao(client, auth_headers, produto):
    variacao = client.post(
        "/produtos/",
        json={
            "codigo": "VAR-ESTOQUE",
            "nome": f"{produto.nome} Estoque Próprio",
            "produto_pai_id": produto.id,
            "preco_custo": "10.00",
            "preco_venda": "20.00",
            "estoque": 7,
        },
        headers=auth_headers,
    ).json()

    pai_depois = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()

    assert variacao["estoque"] == 7
    assert pai_depois["estoque"] == produto.estoque
