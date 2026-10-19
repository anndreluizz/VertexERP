def test_criar_categoria(client, auth_headers):
    response = client.post(
        "/categorias/",
        json={"nome": "Bebidas", "descricao": "Bebidas em geral"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    dados = response.json()

    assert dados["nome"] == "Bebidas"
    assert dados["ativo"] is True


def test_criar_categoria_duplicada(client, auth_headers):
    client.post(
        "/categorias/",
        json={"nome": "Bebidas"},
        headers=auth_headers,
    )

    response = client.post(
        "/categorias/",
        json={"nome": "Bebidas"},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Categoria já cadastrada."


def test_listar_categorias(client, auth_headers):
    client.post(
        "/categorias/",
        json={"nome": "Limpeza"},
        headers=auth_headers,
    )

    response = client.get("/categorias/", headers=auth_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_atualizar_categoria(client, auth_headers):
    criada = client.post(
        "/categorias/",
        json={"nome": "Limpeza"},
        headers=auth_headers,
    ).json()

    response = client.put(
        f"/categorias/{criada['id']}",
        json={"descricao": "Produtos de limpeza"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["descricao"] == "Produtos de limpeza"


def test_atualizar_categoria_inexistente(client, auth_headers):
    response = client.put(
        "/categorias/9999",
        json={"descricao": "x"},
        headers=auth_headers,
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Categoria não encontrada."


def test_excluir_categoria(client, auth_headers):
    criada = client.post(
        "/categorias/",
        json={"nome": "Limpeza"},
        headers=auth_headers,
    ).json()

    response = client.delete(
        f"/categorias/{criada['id']}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    listagem = client.get("/categorias/", headers=auth_headers)

    assert listagem.json() == []


def test_recentes_poe_a_ultima_categoria_usada_primeiro(client, auth_headers, db):
    from app.models.produto import Produto

    for nome in ("Bolsas", "Calcados", "Roupas", "Nunca usada"):
        client.post("/categorias/", json={"nome": nome}, headers=auth_headers)

    def cadastrar(codigo, categoria):
        db.add(Produto(codigo=codigo, nome=codigo, categoria=categoria, unidade="UN",
                       preco_custo=1, preco_venda=2, estoque=0, estoque_minimo=0, ativo=True))
        db.commit()

    def ordem(query=""):
        return [c["nome"] for c in client.get(f"/categorias/{query}", headers=auth_headers).json()]

    cadastrar("A1", "Roupas")
    cadastrar("A2", "CALCADOS")  # o celular manda em maiusculas
    assert ordem("?recentes=true")[:2] == ["Calcados", "Roupas"]

    cadastrar("A3", "Roupas")  # alterna conforme o uso
    assert ordem("?recentes=true")[:2] == ["Roupas", "Calcados"]
    assert ordem("?recentes=true")[-1] == "Nunca usada"
    assert ordem() == ["Bolsas", "Calcados", "Roupas", "Nunca usada"]  # sem o parametro, igual antes
