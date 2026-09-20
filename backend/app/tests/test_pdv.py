def test_buscar_produto_por_codigo(client, auth_headers, produto):
    response = client.get(
        f"/pdv/produto/{produto.codigo}", headers=auth_headers
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["id"] == produto.id
    assert dados["nome"] == produto.nome


def test_buscar_produto_por_codigo_de_barras(client, auth_headers, db):
    from app.models.produto import Produto

    novo = Produto(
        codigo="P200",
        codigo_barras="7891234567890",
        nome="Produto com Código de Barras",
        preco_custo=5.0,
        preco_venda=9.9,
        estoque=20,
        estoque_minimo=2,
        ativo=True,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)

    response = client.get(
        f"/pdv/produto/{novo.codigo_barras}", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["id"] == novo.id


def test_buscar_produto_inexistente(client, auth_headers):
    response = client.get("/pdv/produto/CODIGO-INEXISTENTE", headers=auth_headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "Produto não encontrado."


def test_pdv_usa_preco_promocional_vigente(client, auth_headers, produto, db):
    from datetime import date, timedelta

    produto.preco_promocional = 12.5
    produto.promocao_inicio = date.today() - timedelta(days=1)
    produto.promocao_fim = date.today() + timedelta(days=1)
    db.add(produto)
    db.commit()

    response = client.get(
        f"/pdv/produto/{produto.codigo}", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json()["preco"] == 12.5
