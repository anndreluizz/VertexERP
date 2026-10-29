def test_produtos_respeita_limit_e_skip(client, auth_headers):
    for i in range(5):
        client.post(
            "/produtos/",
            json={
                "codigo": f"PAG{i}",
                "nome": f"Produto Paginado {i}",
                "preco_custo": "1.00",
                "preco_venda": "2.00",
                "estoque": 10,
                "estoque_minimo": 1,
            },
            headers=auth_headers,
        )

    primeira_pagina = client.get(
        "/produtos/?skip=0&limit=2", headers=auth_headers
    ).json()

    segunda_pagina = client.get(
        "/produtos/?skip=2&limit=2", headers=auth_headers
    ).json()

    assert len(primeira_pagina) == 2
    assert len(segunda_pagina) == 2

    # páginas diferentes não se sobrepõem
    ids_primeira = {p["id"] for p in primeira_pagina}
    ids_segunda = {p["id"] for p in segunda_pagina}
    assert ids_primeira.isdisjoint(ids_segunda)


def test_produtos_limit_maximo_e_respeitado(client, auth_headers):
    response = client.get(
        "/produtos/?limit=1000", headers=auth_headers
    )

    assert response.status_code == 422


def test_produtos_limit_padrao_sem_parametros(client, auth_headers, produto):
    response = client.get("/produtos/", headers=auth_headers)

    assert response.status_code == 200
    # comportamento padrão (sem skip/limit) continua igual a antes
    assert len(response.json()) == 1


def test_vendas_respeita_paginacao(
    client, auth_headers, produto, caixa_aberto
):
    for _ in range(3):
        client.post(
            "/vendas/",
            json={
                "forma_pagamento": "DINHEIRO",
                "itens": [
                    {
                        "produto_id": produto.id,
                        "quantidade": 1,
                        "valor_unitario": "5.00",
                    }
                ],
            },
            headers=auth_headers,
        )

    pagina = client.get(
        "/vendas/?skip=1&limit=1", headers=auth_headers
    ).json()

    assert len(pagina) == 1


def test_movimentos_caixa_respeita_paginacao(
    client, auth_headers, caixa_aberto
):
    for _ in range(3):
        client.post(
            "/movimentos-caixa/",
            json={"tipo": "SUPRIMENTO", "descricao": "x", "valor": 10.0},
            headers=auth_headers,
        )

    pagina = client.get(
        "/movimentos-caixa/?skip=1&limit=1", headers=auth_headers
    ).json()

    assert len(pagina) == 1


def test_movimentos_caixa_filtra_por_data_inicio(client, auth_headers, db, usuario, caixa_aberto):
    from datetime import datetime
    from app.models.movimento_caixa import MovimentoCaixa

    for data in (datetime(2025, 1, 10), datetime(2026, 10, 10)):
        db.add(MovimentoCaixa(caixa_id=caixa_aberto.id, usuario_id=usuario.id, tipo="SANGRIA",
                              valor=5, descricao="x", data=data))
    db.commit()

    r = client.get("/movimentos-caixa/?data_inicio=2026-01-01", headers=auth_headers)
    assert r.status_code == 200
    assert [m["data"][:10] for m in r.json()] == ["2026-10-10"]
