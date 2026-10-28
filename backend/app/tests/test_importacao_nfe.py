_XML_NOVO_FORNECEDOR = """<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe Id="NFe1" versao="4.00">
      <emit>
        <CNPJ>11122233000144</CNPJ>
        <xNome>Distribuidora Nova Ltda</xNome>
        <xFant>Distribuidora Nova</xFant>
      </emit>
      <det nItem="1">
        <prod>
          <cProd>NOVO001</cProd>
          <cEAN>SEM GTIN</cEAN>
          <xProd>Produto Importado Novo</xProd>
          <qCom>20.0000</qCom>
          <vUnCom>3.0000</vUnCom>
        </prod>
      </det>
    </infNFe>
  </NFe>
</nfeProc>"""


def _xml_produto_existente(codigo: str, cnpj: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe>
    <infNFe Id="NFe2" versao="4.00">
      <emit>
        <CNPJ>{cnpj}</CNPJ>
        <xNome>Fornecedor Teste Ltda</xNome>
      </emit>
      <det nItem="1">
        <prod>
          <cProd>{codigo}</cProd>
          <cEAN>SEM GTIN</cEAN>
          <xProd>Nome Atualizado do XML</xProd>
          <qCom>7.0000</qCom>
          <vUnCom>11.0000</vUnCom>
        </prod>
      </det>
    </infNFe>
  </NFe>
</nfeProc>"""


def test_preview_nao_grava_nada_no_banco(client, auth_headers, fornecedor, db):
    from app.models.produto import Produto

    total_produtos_antes = db.query(Produto).count()

    response = client.post(
        "/fornecedores/importar-nfe",
        json={"xml_conteudo": _XML_NOVO_FORNECEDOR},
        headers=auth_headers,
    )

    assert response.status_code == 200
    dados = response.json()
    assert dados["fornecedor"]["encontrado"] is False
    assert dados["fornecedor"]["cnpj"] == "11122233000144"
    assert len(dados["itens"]) == 1
    assert dados["itens"][0]["produto_id"] is None

    total_produtos_depois = db.query(Produto).count()
    assert total_produtos_antes == total_produtos_depois


def test_preview_casa_fornecedor_e_produto_existentes(
    client, auth_headers, fornecedor, produto
):
    xml = _xml_produto_existente(produto.codigo, fornecedor.cnpj)

    response = client.post(
        "/fornecedores/importar-nfe",
        json={"xml_conteudo": xml},
        headers=auth_headers,
    )

    assert response.status_code == 200
    dados = response.json()

    assert dados["fornecedor"]["encontrado"] is True
    assert dados["fornecedor"]["id"] == fornecedor.id

    item = dados["itens"][0]
    assert item["produto_id"] == produto.id
    # margem do fornecedor (20%) aplicada sobre custo 11.00 -> 13.20
    assert item["preco_sugerido"] == 13.2


def test_confirmar_cria_fornecedor_novo_e_produto_novo(client, auth_headers, db):
    from app.models.fornecedor import Fornecedor
    from app.models.produto import Produto

    response = client.post(
        "/compras/importar-nfe",
        json={
            "fornecedor_novo": {
                "razao_social": "Distribuidora Nova Ltda",
                "cnpj": "11122233000144",
                "margem_padrao": "40.00",
            },
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": None,
                    "codigo": "NOVO001",
                    "descricao": "Produto Importado Novo",
                    "quantidade": 20,
                    "custo": "3.00",
                    "preco_venda": "4.20",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    compra = response.json()
    assert float(compra["valor_total"]) == 60.0

    fornecedor_criado = (
        db.query(Fornecedor).filter(Fornecedor.cnpj == "11122233000144").first()
    )
    assert fornecedor_criado is not None

    produto_criado = (
        db.query(Produto).filter(Produto.codigo == "NOVO001").first()
    )
    assert produto_criado is not None
    assert produto_criado.estoque == 20
    assert float(produto_criado.preco_custo) == 3.0
    assert float(produto_criado.preco_venda) == 4.2


def test_confirmar_atualiza_produto_existente_e_soma_estoque(
    client, auth_headers, fornecedor, produto, db
):
    estoque_inicial = produto.estoque

    response = client.post(
        "/compras/importar-nfe",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": produto.id,
                    "codigo": produto.codigo,
                    "descricao": produto.nome,
                    "quantidade": 7,
                    "custo": "11.00",
                    "preco_venda": "13.20",
                    "atualizar_preco_venda": True,
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    produto_atualizado = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()

    assert produto_atualizado["estoque"] == estoque_inicial + 7
    assert float(produto_atualizado["preco_custo"]) == 11.0
    assert float(produto_atualizado["preco_venda"]) == 13.2


def test_confirmar_sem_pedir_nao_mexe_no_preco_de_venda_existente(
    client, auth_headers, fornecedor, produto, db
):
    """Sem atualizar_preco_venda, produto ja cadastrado so' ganha custo
    e estoque novos -- o preco de venda da loja fica como estava."""

    preco_venda_antes = float(produto.preco_venda)

    response = client.post(
        "/compras/importar-nfe",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": produto.id,
                    "codigo": produto.codigo,
                    "descricao": produto.nome,
                    "quantidade": 3,
                    "custo": "11.00",
                    # margem 0%: preco de venda = custo
                    "preco_venda": "11.00",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200

    produto_atualizado = client.get(
        f"/produtos/{produto.id}", headers=auth_headers
    ).json()

    assert float(produto_atualizado["preco_custo"]) == 11.0
    assert float(produto_atualizado["preco_venda"]) == preco_venda_antes


def test_confirmar_sem_fornecedor_da_erro(client, auth_headers, produto):
    response = client.post(
        "/compras/importar-nfe",
        json={
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": produto.id,
                    "codigo": produto.codigo,
                    "descricao": produto.nome,
                    "quantidade": 1,
                    "custo": "1.00",
                    "preco_venda": "1.50",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_confirmar_produto_inexistente_da_erro(client, auth_headers, fornecedor):
    response = client.post(
        "/compras/importar-nfe",
        json={
            "fornecedor_id": fornecedor.id,
            "forma_pagamento": "DINHEIRO",
            "itens": [
                {
                    "produto_id": 999999,
                    "codigo": "X",
                    "descricao": "X",
                    "quantidade": 1,
                    "custo": "1.00",
                    "preco_venda": "1.50",
                }
            ],
        },
        headers=auth_headers,
    )

    assert response.status_code == 400


def test_confirmar_no_boleto_gera_parcelas_mensais_e_categoria(client, auth_headers, db):
    """Pedido da Ultra Jeans: 'Boleto' nao gerava Contas a Pagar e o
    produto novo vinha sem categoria."""
    from app.models.conta_pagar import ContaPagar
    from app.models.produto import Produto

    response = client.post(
        "/compras/importar-nfe",
        json={
            "fornecedor_novo": {"razao_social": "Ultra Teste Ltda", "cnpj": "37852542000100"},
            "forma_pagamento": "BOLETO",
            "data_vencimento": "2026-12-05T00:00:00",
            "numero_parcelas": 4,
            "categoria": "ROUPA",
            "itens": [{
                "produto_id": None, "codigo": "UJ096204", "descricao": "MEIA COXA",
                "quantidade": 5, "custo": "105.00", "preco_venda": "189.90",
            }],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    compra_id = response.json()["id"]
    contas = (db.query(ContaPagar).filter(ContaPagar.compra_id == compra_id)
              .order_by(ContaPagar.data_vencimento).all())
    assert [c.data_vencimento.strftime("%d/%m/%Y") for c in contas] == [
        "05/12/2026", "05/01/2027", "05/02/2027", "05/03/2027"]
    assert sum(float(c.valor) for c in contas) == 525.0
    assert db.query(Produto).filter(Produto.codigo == "UJ096204").first().categoria == "ROUPA"
