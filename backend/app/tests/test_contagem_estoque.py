def _criar_loja(db):
    from app.models.loja import Loja

    loja = Loja(nome="Loja Contagem")
    db.add(loja)
    db.commit()
    return loja


def test_abrir_contagem_faz_snapshot_do_estoque_atual(
    client, auth_headers, produto, db
):
    from app.models.estoque_loja import EstoqueLoja

    loja = _criar_loja(db)
    db.add(EstoqueLoja(produto_id=produto.id, loja_id=loja.id, quantidade=15))
    db.commit()

    response = client.post(
        f"/estoque/contagens?loja_id={loja.id}",
        json={"observacao": "Contagem mensal"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    dados = response.json()
    assert dados["status"] == "ABERTA"
    assert dados["loja_id"] == loja.id

    item = next(i for i in dados["itens"] if i["produto_id"] == produto.id)
    assert item["quantidade_sistema"] == 15
    assert item["quantidade_contada"] is None


def test_abrir_contagem_com_uma_ja_aberta_falha(client, auth_headers, db):
    loja = _criar_loja(db)

    client.post(
        f"/estoque/contagens?loja_id={loja.id}", json={}, headers=auth_headers
    )
    response = client.post(
        f"/estoque/contagens?loja_id={loja.id}", json={}, headers=auth_headers
    )

    assert response.status_code == 400


def test_contagem_aberta_retorna_null_sem_contagem(client, auth_headers, db):
    loja = _criar_loja(db)

    response = client.get(
        f"/estoque/contagens/aberta?loja_id={loja.id}", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json() is None


def test_registrar_item_e_finalizar_gera_ajuste_de_estoque(
    client, auth_headers, produto, db
):
    from app.models.estoque_loja import EstoqueLoja

    loja = _criar_loja(db)
    db.add(EstoqueLoja(produto_id=produto.id, loja_id=loja.id, quantidade=15))
    db.commit()

    contagem = client.post(
        f"/estoque/contagens?loja_id={loja.id}", json={}, headers=auth_headers
    ).json()
    item = next(i for i in contagem["itens"] if i["produto_id"] == produto.id)

    resp_item = client.put(
        f"/estoque/contagens/{contagem['id']}/itens/{item['id']}",
        json={"quantidade_contada": 12},
        headers=auth_headers,
    )
    assert resp_item.status_code == 200
    assert resp_item.json()["quantidade_contada"] == 12

    resp_final = client.post(
        f"/estoque/contagens/{contagem['id']}/finalizar", headers=auth_headers
    )
    assert resp_final.status_code == 200
    assert resp_final.json()["status"] == "FINALIZADA"

    qtd_final = (
        db.query(EstoqueLoja)
        .filter(
            EstoqueLoja.produto_id == produto.id, EstoqueLoja.loja_id == loja.id
        )
        .first()
        .quantidade
    )
    assert qtd_final == 12


def test_finalizar_ignora_itens_nao_contados(client, auth_headers, produto, db):
    from app.models.estoque_loja import EstoqueLoja

    loja = _criar_loja(db)
    db.add(EstoqueLoja(produto_id=produto.id, loja_id=loja.id, quantidade=15))
    db.commit()

    contagem = client.post(
        f"/estoque/contagens?loja_id={loja.id}", json={}, headers=auth_headers
    ).json()

    client.post(
        f"/estoque/contagens/{contagem['id']}/finalizar", headers=auth_headers
    )

    qtd_final = (
        db.query(EstoqueLoja)
        .filter(
            EstoqueLoja.produto_id == produto.id, EstoqueLoja.loja_id == loja.id
        )
        .first()
        .quantidade
    )
    assert qtd_final == 15


def test_finalizar_contagem_ja_encerrada_falha(client, auth_headers, db):
    loja = _criar_loja(db)

    contagem = client.post(
        f"/estoque/contagens?loja_id={loja.id}", json={}, headers=auth_headers
    ).json()
    client.post(f"/estoque/contagens/{contagem['id']}/finalizar", headers=auth_headers)

    response = client.post(
        f"/estoque/contagens/{contagem['id']}/finalizar", headers=auth_headers
    )

    assert response.status_code == 400


def test_cancelar_contagem_nao_gera_ajuste(client, auth_headers, produto, db):
    from app.models.estoque_loja import EstoqueLoja

    loja = _criar_loja(db)
    db.add(EstoqueLoja(produto_id=produto.id, loja_id=loja.id, quantidade=15))
    db.commit()

    contagem = client.post(
        f"/estoque/contagens?loja_id={loja.id}", json={}, headers=auth_headers
    ).json()
    item = next(i for i in contagem["itens"] if i["produto_id"] == produto.id)

    client.put(
        f"/estoque/contagens/{contagem['id']}/itens/{item['id']}",
        json={"quantidade_contada": 999},
        headers=auth_headers,
    )

    response = client.post(
        f"/estoque/contagens/{contagem['id']}/cancelar", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELADA"

    qtd_final = (
        db.query(EstoqueLoja)
        .filter(
            EstoqueLoja.produto_id == produto.id, EstoqueLoja.loja_id == loja.id
        )
        .first()
        .quantidade
    )
    assert qtd_final == 15

    # nova contagem pode ser aberta depois de cancelar a anterior
    response = client.post(
        f"/estoque/contagens?loja_id={loja.id}", json={}, headers=auth_headers
    )
    assert response.status_code == 201


def test_listar_contagens(client, auth_headers, db):
    loja = _criar_loja(db)

    client.post(
        f"/estoque/contagens?loja_id={loja.id}", json={}, headers=auth_headers
    )

    response = client.get("/estoque/contagens", headers=auth_headers)

    assert response.status_code == 200
    assert len(response.json()) >= 1
