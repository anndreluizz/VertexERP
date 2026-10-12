def _criar_lojas(db):
    from app.models.loja import Loja

    origem = Loja(nome="Loja Origem")
    destino = Loja(nome="Loja Destino")
    db.add_all([origem, destino])
    db.commit()
    return origem, destino


def test_transferencia_move_estoque_entre_lojas(client, auth_headers, produto, db):
    from app.models.estoque_loja import EstoqueLoja

    origem, destino = _criar_lojas(db)

    db.add(
        EstoqueLoja(
            produto_id=produto.id, loja_id=origem.id, quantidade=20
        )
    )
    db.commit()

    response = client.post(
        f"/estoque/transferencias?loja_id={origem.id}",
        json={
            "produto_id": produto.id,
            "loja_destino_id": destino.id,
            "quantidade": 8,
            "motivo": "Reposição",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    dados = response.json()
    assert dados["loja_origem_id"] == origem.id
    assert dados["loja_destino_id"] == destino.id
    assert dados["quantidade"] == 8

    qtd_origem = (
        db.query(EstoqueLoja)
        .filter(
            EstoqueLoja.produto_id == produto.id,
            EstoqueLoja.loja_id == origem.id,
        )
        .first()
        .quantidade
    )
    qtd_destino = (
        db.query(EstoqueLoja)
        .filter(
            EstoqueLoja.produto_id == produto.id,
            EstoqueLoja.loja_id == destino.id,
        )
        .first()
        .quantidade
    )

    assert qtd_origem == 12
    assert qtd_destino == 8


def test_transferencia_gera_dois_movimentos_ligados(
    client, auth_headers, produto, db
):
    from app.models.estoque_loja import EstoqueLoja

    origem, destino = _criar_lojas(db)
    db.add(EstoqueLoja(produto_id=produto.id, loja_id=origem.id, quantidade=10))
    db.commit()

    resp = client.post(
        f"/estoque/transferencias?loja_id={origem.id}",
        json={
            "produto_id": produto.id,
            "loja_destino_id": destino.id,
            "quantidade": 5,
        },
        headers=auth_headers,
    )
    transferencia_id = resp.json()["id"]

    movimentos = client.get(
        f"/estoque/movimentos/produto/{produto.id}", headers=auth_headers
    ).json()

    ligados = [
        m for m in movimentos if m.get("transferencia_id") == transferencia_id
    ]
    assert len(ligados) == 2
    assert {m["tipo"] for m in ligados} == {"ENTRADA", "SAIDA"}


def test_transferencia_estoque_insuficiente_nao_grava_nada(
    client, auth_headers, produto, db
):
    from app.models.estoque_loja import EstoqueLoja
    from app.models.transferencia_estoque import TransferenciaEstoque

    origem, destino = _criar_lojas(db)
    db.add(EstoqueLoja(produto_id=produto.id, loja_id=origem.id, quantidade=3))
    db.commit()

    total_antes = db.query(TransferenciaEstoque).count()

    response = client.post(
        f"/estoque/transferencias?loja_id={origem.id}",
        json={
            "produto_id": produto.id,
            "loja_destino_id": destino.id,
            "quantidade": 100,
        },
        headers=auth_headers,
    )

    assert response.status_code == 400

    total_depois = db.query(TransferenciaEstoque).count()
    assert total_antes == total_depois

    qtd_origem = (
        db.query(EstoqueLoja)
        .filter(
            EstoqueLoja.produto_id == produto.id,
            EstoqueLoja.loja_id == origem.id,
        )
        .first()
        .quantidade
    )
    assert qtd_origem == 3


def test_transferencia_mesma_loja_origem_destino_falha(
    client, auth_headers, produto, db
):
    origem, _ = _criar_lojas(db)

    response = client.post(
        f"/estoque/transferencias?loja_id={origem.id}",
        json={
            "produto_id": produto.id,
            "loja_destino_id": origem.id,
            "quantidade": 1,
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_listar_transferencias(client, auth_headers, produto, db):
    from app.models.estoque_loja import EstoqueLoja

    origem, destino = _criar_lojas(db)
    db.add(EstoqueLoja(produto_id=produto.id, loja_id=origem.id, quantidade=10))
    db.commit()

    client.post(
        f"/estoque/transferencias?loja_id={origem.id}",
        json={
            "produto_id": produto.id,
            "loja_destino_id": destino.id,
            "quantidade": 2,
        },
        headers=auth_headers,
    )

    response = client.get("/estoque/transferencias", headers=auth_headers)

    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_produto_cadastrado_numa_loja_aparece_na_outra_e_transfere(
    client, auth_headers, db
):
    """Catalogo unico: produto cadastrado na origem (estoque 10 la)
    aparece na destino com estoque 0, e a transferencia chega nela."""
    origem, destino = _criar_lojas(db)

    criado = client.post(
        f"/produtos/?loja_id={origem.id}",
        json={"codigo": "T900", "nome": "Bolsa", "preco_custo": "10",
              "preco_venda": "20", "estoque": 10},
        headers=auth_headers,
    )
    assert criado.status_code == 201
    assert criado.json()["loja_id"] is None

    def estoque_na(loja):
        lista = client.get(f"/produtos/?loja_id={loja.id}", headers=auth_headers).json()
        return next(p["estoque"] for p in lista if p["codigo"] == "T900")

    assert estoque_na(destino) == 0

    response = client.post(
        f"/estoque/transferencias?loja_id={origem.id}",
        json={"produto_id": criado.json()["id"], "loja_destino_id": destino.id,
              "quantidade": 4},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert estoque_na(origem) == 6
    assert estoque_na(destino) == 4

    repetido = client.post(
        f"/produtos/?loja_id={destino.id}",
        json={"codigo": "T900", "nome": "Outro", "preco_custo": "1",
              "preco_venda": "2"},
        headers=auth_headers,
    )
    assert repetido.status_code == 400


def test_produto_exclusivo_nao_transfere(client, auth_headers, produto, db):
    from app.models.estoque_loja import EstoqueLoja

    origem, destino = _criar_lojas(db)
    produto.loja_id = origem.id
    db.add(EstoqueLoja(produto_id=produto.id, loja_id=origem.id, quantidade=10))
    db.commit()

    response = client.post(
        f"/estoque/transferencias?loja_id={origem.id}",
        json={"produto_id": produto.id, "loja_destino_id": destino.id,
              "quantidade": 2},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "exclusivo" in response.json()["detail"]
