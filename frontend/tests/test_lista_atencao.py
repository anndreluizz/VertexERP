"""Faixa 'Atencao hoje' e ficha rapida das telas de lista (design/lista.py)."""
from design.lista import FaixaAtencao, PainelDetalhe
from telas import produtos as tela
from telas.produtos import Produtos


def _produto(id_, nome, estoque, minimo=5):
    return {"id": id_, "nome": nome, "codigo": f"{id_:04d}", "estoque": estoque,
            "estoque_minimo": minimo, "preco_venda": 20.0, "preco_custo": 10.0,
            "categoria": "Papelaria", "ativo": True, "na_loja": True}


def test_faixa_some_sem_avisos_e_aparece_com_aviso():
    faixa = FaixaAtencao()
    faixa.definir([])
    assert faixa.isHidden()

    cliques = []
    faixa.definir([("2 vencidas", "Ver lista", lambda: cliques.append(1))])
    assert not faixa.isHidden()

    faixa.definir([])
    assert faixa.isHidden()


def test_painel_detalhe_abre_e_fecha():
    painel = PainelDetalhe()
    assert painel.isHidden()
    acoes = []
    painel.mostrar("Maria", "tel", ("Em dia", "sucesso"), [("Saldo", "R$ 1,00", None)],
                   [("Editar", "primario", "edit-2", lambda: acoes.append(1))], ("Uso", 50, "#000"))
    assert not painel.isHidden()
    painel.esconder()
    assert painel.isHidden()


def test_produtos_faixa_conta_sem_estoque_e_estoque_baixo(monkeypatch):
    monkeypatch.setattr(tela.api, "usuario_tem_permissao", lambda _p: True)
    w = Produtos()
    w._ao_carregar_sucesso(([_produto(1, "A", 0), _produto(2, "B", 3), _produto(3, "C", 30)], []))
    assert not w.faixa_atencao.isHidden()

    w._ao_carregar_sucesso(([_produto(3, "C", 30)], []))
    assert w.faixa_atencao.isHidden()


def test_produtos_clique_na_linha_abre_ficha_e_checkbox_nao(monkeypatch):
    monkeypatch.setattr(tela.api, "usuario_tem_permissao", lambda _p: True)
    w = Produtos()
    w._ao_carregar_sucesso(([_produto(1, "A", 0), _produto(2, "B", 30)], []))
    assert w.painel_detalhe.isHidden()

    w._ao_clicar_linha(0, 0)   # coluna do checkbox: nao abre
    assert w.painel_detalhe.isHidden()

    w._ao_clicar_linha(0, 3)
    assert not w.painel_detalhe.isHidden()

    # repopular a tabela (filtro, busca) fecha a ficha: ela ficaria desatualizada
    w.filtrar_produtos()
    assert w.painel_detalhe.isHidden()
