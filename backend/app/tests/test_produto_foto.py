import base64

_IMAGEM_FAKE = base64.b64encode(b"fake-jpeg-bytes").decode("ascii")


def _adicionar_foto(client, auth_headers, produto_id, principal=False):
    return client.post(
        f"/produtos/{produto_id}/fotos",
        json={"imagem_base64": _IMAGEM_FAKE, "principal": principal},
        headers=auth_headers,
    )


def test_primeira_foto_fica_principal_mesmo_sem_pedir(
    client, auth_headers, produto
):
    response = _adicionar_foto(client, auth_headers, produto.id)

    assert response.status_code == 201
    assert response.json()["principal"] is True


def test_segunda_foto_nao_principal_por_padrao(client, auth_headers, produto):
    _adicionar_foto(client, auth_headers, produto.id)
    segunda = _adicionar_foto(client, auth_headers, produto.id)

    assert segunda.json()["principal"] is False

    fotos = client.get(
        f"/produtos/{produto.id}/fotos", headers=auth_headers
    ).json()
    assert sum(1 for f in fotos if f["principal"]) == 1


def test_marcar_outra_foto_como_principal(client, auth_headers, produto):
    primeira = _adicionar_foto(client, auth_headers, produto.id).json()
    segunda = _adicionar_foto(client, auth_headers, produto.id).json()

    response = client.put(
        f"/produtos/{produto.id}/fotos/{segunda['id']}/principal",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["principal"] is True

    fotos = client.get(
        f"/produtos/{produto.id}/fotos", headers=auth_headers
    ).json()
    por_id = {f["id"]: f for f in fotos}
    assert por_id[primeira["id"]]["principal"] is False
    assert por_id[segunda["id"]]["principal"] is True


def test_remover_foto_principal_promove_proxima(client, auth_headers, produto):
    primeira = _adicionar_foto(client, auth_headers, produto.id).json()
    segunda = _adicionar_foto(client, auth_headers, produto.id).json()

    response = client.delete(
        f"/produtos/{produto.id}/fotos/{primeira['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 200

    fotos = client.get(
        f"/produtos/{produto.id}/fotos", headers=auth_headers
    ).json()
    assert len(fotos) == 1
    assert fotos[0]["id"] == segunda["id"]
    assert fotos[0]["principal"] is True


def test_listar_fotos_vazio_quando_produto_nao_tem_foto(
    client, auth_headers, produto
):
    response = client.get(
        f"/produtos/{produto.id}/fotos", headers=auth_headers
    )

    assert response.status_code == 200
    assert response.json() == []


def test_cadastrar_produto_com_foto_sincroniza_galeria(client, auth_headers):
    response = client.post(
        "/produtos/",
        json={
            "codigo": "FOTO-SYNC-001",
            "nome": "Produto Com Foto",
            "categoria": "Geral",
            "preco_custo": "1.00",
            "preco_venda": "2.00",
            "foto_base64": _IMAGEM_FAKE,
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    produto_id = response.json()["id"]

    fotos = client.get(
        f"/produtos/{produto_id}/fotos", headers=auth_headers
    ).json()

    assert len(fotos) == 1
    assert fotos[0]["principal"] is True


def test_atualizar_foto_do_produto_atualiza_a_principal_existente(
    client, auth_headers, produto
):
    _adicionar_foto(client, auth_headers, produto.id)

    outra_imagem = base64.b64encode(b"outra-imagem").decode("ascii")

    client.put(
        f"/produtos/{produto.id}",
        json={
            "codigo": produto.codigo,
            "nome": produto.nome,
            "categoria": produto.categoria,
            "preco_custo": str(produto.preco_custo),
            "preco_venda": str(produto.preco_venda),
            "foto_base64": outra_imagem,
            "ativo": True,
        },
        headers=auth_headers,
    )

    fotos = client.get(
        f"/produtos/{produto.id}/fotos", headers=auth_headers
    ).json()

    # continua so' 1 foto (a principal foi atualizada, nao duplicada)
    assert len(fotos) == 1
    assert fotos[0]["principal"] is True
