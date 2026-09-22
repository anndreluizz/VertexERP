def _csv(linhas):
    """linhas: lista de listas de string -- monta o texto separado por
    ';' (mesmo delimitador do exportar_csv do frontend)."""
    return "\n".join(";".join(campo) for campo in linhas)


CABECALHO = [
    "Código", "Nome", "Categoria", "Código de Barras",
    "Preço de Custo", "Preço de Venda", "Estoque", "Estoque Mínimo",
    "Unidade",
]


def test_preview_linha_nova_sem_erro(client, auth_headers):
    csv_conteudo = _csv([
        CABECALHO,
        ["", "Camiseta Branca", "Roupa", "", "15.00", "39.90", "10", "2", "UN"],
    ])

    response = client.post(
        "/produtos/importar-csv/preview",
        json={"csv_conteudo": csv_conteudo},
        headers=auth_headers,
    )

    assert response.status_code == 200
    dados = response.json()

    assert dados["total_novos"] == 1
    assert dados["total_atualizados"] == 0
    assert dados["total_com_erro"] == 0

    item = dados["itens"][0]
    assert item["nome"] == "Camiseta Branca"
    assert item["produto_id"] is None
    assert item["codigo"].startswith("PROD-")
    assert float(item["preco_venda"]) == 39.9


def test_preview_casa_produto_existente_pelo_codigo(client, auth_headers, produto):
    csv_conteudo = _csv([
        CABECALHO,
        [produto.codigo, "Nome Atualizado", "", "", "12.00", "25.00", "5", "1", "UN"],
    ])

    response = client.post(
        "/produtos/importar-csv/preview",
        json={"csv_conteudo": csv_conteudo},
        headers=auth_headers,
    )

    dados = response.json()
    assert dados["total_atualizados"] == 1
    assert dados["itens"][0]["produto_id"] == produto.id


def test_preview_casa_produto_existente_pelo_codigo_barras(
    client, auth_headers, db, produto
):
    produto.codigo_barras = "7891234567890"
    db.commit()

    csv_conteudo = _csv([
        CABECALHO,
        ["", "Outro Nome", "", "7891234567890", "1.00", "2.00", "0", "0", "UN"],
    ])

    response = client.post(
        "/produtos/importar-csv/preview",
        json={"csv_conteudo": csv_conteudo},
        headers=auth_headers,
    )

    dados = response.json()
    assert dados["itens"][0]["produto_id"] == produto.id


def test_preview_marca_erro_de_nome_vazio_e_preco_invalido(client, auth_headers):
    csv_conteudo = _csv([
        CABECALHO,
        ["", "", "", "", "abc", "39.90", "10", "2", "UN"],
    ])

    response = client.post(
        "/produtos/importar-csv/preview",
        json={"csv_conteudo": csv_conteudo},
        headers=auth_headers,
    )

    dados = response.json()
    assert dados["total_com_erro"] == 1
    assert "nome vazio" in dados["itens"][0]["erro"]
    assert "abc" in dados["itens"][0]["erro"]


def test_preview_tolera_cabecalho_sem_acento_e_minusculo(client, auth_headers):
    csv_conteudo = _csv([
        ["codigo", "nome", "categoria", "codigo de barras",
         "preco de custo", "preco de venda", "estoque", "estoque minimo", "unidade"],
        ["", "Produto Sem Acento", "", "", "1", "2", "3", "0", "UN"],
    ])

    response = client.post(
        "/produtos/importar-csv/preview",
        json={"csv_conteudo": csv_conteudo},
        headers=auth_headers,
    )

    dados = response.json()
    assert dados["total_novos"] == 1
    assert dados["itens"][0]["nome"] == "Produto Sem Acento"


def test_confirmar_cria_produtos_novos(client, auth_headers):
    response = client.post(
        "/produtos/importar-csv/confirmar",
        json={
            "itens": [{
                "codigo": "IMP-001", "nome": "Produto Importado",
                "categoria": "Roupa", "codigo_barras": None,
                "preco_custo": "10.00", "preco_venda": "20.00",
                "estoque": 5, "estoque_minimo": 1, "unidade": "UN",
                "produto_id": None,
            }],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    dados = response.json()
    assert dados["criados"] == 1
    assert dados["atualizados"] == 0

    listagem = client.get("/produtos/", headers=auth_headers).json()
    assert any(p["codigo"] == "IMP-001" for p in listagem)


def test_confirmar_atualiza_produto_existente(client, auth_headers, produto):
    response = client.post(
        "/produtos/importar-csv/confirmar",
        json={
            "itens": [{
                "codigo": produto.codigo, "nome": "Nome Atualizado via CSV",
                "categoria": produto.categoria, "codigo_barras": None,
                "preco_custo": "11.00", "preco_venda": "22.00",
                "estoque": produto.estoque, "estoque_minimo": produto.estoque_minimo,
                "unidade": "UN", "produto_id": produto.id,
            }],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    dados = response.json()
    assert dados["criados"] == 0
    assert dados["atualizados"] == 1

    atualizado = client.get(f"/produtos/{produto.id}", headers=auth_headers).json()
    assert atualizado["nome"] == "Nome Atualizado via CSV"
    assert float(atualizado["preco_venda"]) == 22.0
