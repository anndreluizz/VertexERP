from datetime import date, datetime, timedelta

from app.models.item_venda import ItemVenda
from app.models.produto import Produto
from app.models.produto_foto import ProdutoFoto
from app.models.venda import Venda


def _produto(db, codigo, **extra):
    dados = dict(
        codigo=codigo, nome=f"Produto {codigo}", categoria="Roupas",
        preco_custo=10, preco_venda=50, estoque=3, ativo=True,
        vitrine_publicar=True,
    )
    dados.update(extra)
    novo = Produto(**dados)
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


def _vender(db, produto, quantidade, status="FINALIZADA"):
    venda = Venda(
        valor_total=10, desconto=0, forma_pagamento="DINHEIRO",
        status=status, data=datetime.now(),
    )
    db.add(venda)
    db.flush()
    db.add(ItemVenda(
        venda_id=venda.id, produto_id=produto.id, quantidade=quantidade,
        valor_unitario=10, subtotal=10,
    ))
    db.commit()


def test_so_produto_ativo_e_publicado_aparece_sem_login(client, db):
    _produto(db, "V1")
    _produto(db, "V2", vitrine_publicar=False)
    _produto(db, "V3", ativo=False)

    resposta = client.get("/vitrine/")

    assert resposta.status_code == 200
    assert [p["codigo"] for p in resposta.json()["produtos"]] == ["V1"]


def test_nao_expoe_custo_nem_estoque(client, db):
    _produto(db, "V1")

    item = client.get("/vitrine/").json()["produtos"][0]

    assert "preco_custo" not in item
    assert "estoque" not in item
    assert item["disponibilidade"] == "disponivel"


def test_promocao_valendo_mostra_preco_anterior(client, db):
    _produto(
        db, "V1", preco_promocional=39.9,
        promocao_inicio=date.today(), promocao_fim=date.today() + timedelta(days=3),
    )
    _produto(
        db, "V2", preco_promocional=39.9,
        promocao_fim=date.today() - timedelta(days=1),
    )

    por_codigo = {p["codigo"]: p for p in client.get("/vitrine/").json()["produtos"]}

    assert por_codigo["V1"]["preco"] == 39.9
    assert por_codigo["V1"]["preco_anterior"] == 50
    assert por_codigo["V2"]["preco"] == 50
    assert por_codigo["V2"]["preco_anterior"] is None


def test_disponibilidade_esgotado_e_kit(client, db):
    _produto(db, "V1", estoque=0)
    _produto(db, "V2", estoque=0, eh_kit=True)

    por_codigo = {p["codigo"]: p for p in client.get("/vitrine/").json()["produtos"]}

    assert por_codigo["V1"]["disponibilidade"] == "esgotado"
    assert por_codigo["V2"]["disponibilidade"] == "consulte"


def test_foto_so_sai_de_produto_publicado(client, db):
    publicado = _produto(db, "V1")
    escondido = _produto(db, "V2", vitrine_publicar=False)
    foto_ok = ProdutoFoto(produto_id=publicado.id, imagem=b"jpg-ok", principal=True)
    foto_escondida = ProdutoFoto(produto_id=escondido.id, imagem=b"jpg-x", principal=True)
    db.add_all([foto_ok, foto_escondida])
    db.commit()

    item = client.get("/vitrine/").json()["produtos"][0]
    assert item["fotos"] == [f"/vitrine/fotos/{foto_ok.id}"]

    assert client.get(f"/vitrine/fotos/{foto_ok.id}").content == b"jpg-ok"
    assert client.get(f"/vitrine/fotos/{foto_escondida.id}").status_code == 404


def test_mais_vendidos_ignora_cancelada_e_nao_publicado(client, db):
    a, b = _produto(db, "V1"), _produto(db, "V2")
    escondido = _produto(db, "V3", vitrine_publicar=False)
    _vender(db, a, 1)
    _vender(db, b, 3)
    _vender(db, a, 10, status="CANCELADA")
    _vender(db, escondido, 50)

    assert client.get("/vitrine/").json()["mais_vendidos"] == [b.id, a.id]


def test_publicar_pelo_cadastro_e_editar_sem_o_campo_mantem(client, auth_headers, produto):
    dados = {
        "codigo": produto.codigo, "nome": produto.nome,
        "preco_venda": 20, "vitrine_publicar": True, "vitrine_destaque": True,
    }
    assert client.put(f"/produtos/{produto.id}", json=dados, headers=auth_headers).status_code == 200

    # app mobile antigo nao manda os campos da vitrine
    sem_campo = {"codigo": produto.codigo, "nome": "Novo nome", "preco_venda": 25}
    client.put(f"/produtos/{produto.id}", json=sem_campo, headers=auth_headers)

    item = client.get("/vitrine/").json()["produtos"][0]
    assert item["nome"] == "Novo nome"
    assert item["preco"] == 25
    assert item["destaque"] is True
