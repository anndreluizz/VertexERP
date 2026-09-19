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
