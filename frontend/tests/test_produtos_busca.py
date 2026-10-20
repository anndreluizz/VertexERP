"""Leitor de codigo de barras na busca de Produtos: nao remonta a tabela
a cada digito (era 15 s por leitura com 300 produtos e fotos)."""
from telas import produtos as tela
from telas.produtos import Produtos


def _produto(id_):
    return {"id": id_, "nome": f"PRODUTO {id_}", "codigo": f"{id_:04d}",
            "codigo_barras": f"7891000{id_:06d}", "estoque": 5, "estoque_minimo": 0,
            "preco_venda": 10, "preco_custo": 0, "categoria": None, "ativo": True,
            "na_loja": True}


def test_digitos_do_leitor_nao_filtram_um_a_um_e_enter_filtra_na_hora(monkeypatch):
    monkeypatch.setattr(tela.api, "usuario_tem_permissao", lambda _p: True)
    w = Produtos()
    w._ao_carregar_sucesso(([_produto(i) for i in range(30)], []))
    montagens = []
    original = w.preencher_tabela
    monkeypatch.setattr(w, "preencher_tabela", lambda ps: (montagens.append(len(ps)), original(ps)))

    for digito in "7891000000017":
        w.pesquisa.insert(digito)
    assert montagens == []  # ainda esperando a digitacao parar

    w.pesquisa.returnPressed.emit()
    assert montagens == [1]
    assert not w._timer_busca.isActive()  # o Enter ja' filtrou: nao filtra de novo depois
