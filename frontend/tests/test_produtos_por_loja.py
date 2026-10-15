"""Catalogo unico entre lojas: a tela de Produtos so' lista o que a loja
deste terminal tem (na_loja), com opcao de ver o resto."""
from telas import produtos as tela
from telas.produtos import Produtos


def _produto(id_, nome, estoque, na_loja=True):
    return {"id": id_, "nome": nome, "codigo": f"{id_:04d}", "estoque": estoque,
            "estoque_minimo": 0, "preco_venda": 10, "preco_custo": 0,
            "categoria": None, "ativo": True, "na_loja": na_loja}


def test_esconde_produtos_de_outras_lojas(monkeypatch):
    monkeypatch.setattr(tela.api, "usuario_tem_permissao", lambda _p: True)
    w = Produtos()
    w._ao_carregar_sucesso((
        [_produto(1, "CONJUNTO", 4), _produto(2, "MOLETOM", 0, na_loja=False)],
        [],
    ))

    assert [p["id"] for p in w.produtos] == [1]
    assert not w.chk_outras_lojas.isHidden()
    assert w.chk_outras_lojas.text().endswith("(1)")

    w.chk_outras_lojas.setChecked(True)
    assert [p["id"] for p in w.produtos] == [1, 2]


def test_sem_produtos_de_outras_lojas_nem_mostra_a_opcao(monkeypatch):
    monkeypatch.setattr(tela.api, "usuario_tem_permissao", lambda _p: True)
    w = Produtos()
    w._ao_carregar_sucesso(([_produto(1, "CONJUNTO", 4)], []))

    assert [p["id"] for p in w.produtos] == [1]
    assert w.chk_outras_lojas.isHidden()
