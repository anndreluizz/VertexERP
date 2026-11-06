"""Vertex 2.0: menu do topo agrupado (no lugar do menu lateral)."""
from design.menu_topo import GRUPOS, BarraMenu
from telas.principal import ITENS_MENU, PERMISSAO_TELA


def test_toda_tela_do_menu_esta_num_grupo():
    # sem grupo a tela fica inalcancavel (nao existe mais menu lateral)
    nos_grupos = [c for _, _, chaves in GRUPOS for c in chaves]
    assert len(nos_grupos) == len(set(nos_grupos))
    assert set(nos_grupos) == {c for c, _, _ in ITENS_MENU}


def test_vendedor_nao_ve_telas_de_admin_e_grupo_vazio_some():
    barra = BarraMenu("Loja", ITENS_MENU, lambda c: c not in PERMISSAO_TELA)
    telas = set(barra._grupo_de)
    assert {"dashboard", "pdv", "clientes", "produtos"} <= telas
    # grupo que sobrou com 1 tela so' vira botao direto, sem painel
    assert "Pessoas" in barra.botoes and "Pessoas" not in barra.paineis
    assert not telas & set(PERMISSAO_TELA)
    assert "Financeiro" not in barra.botoes and "Ajustes" not in barra.botoes


def test_item_do_painel_e_botao_direto_emitem_a_tela():
    barra = BarraMenu("Loja", ITENS_MENU, lambda c: True)
    abertas = []
    barra.item_clicado.connect(abertas.append)

    barra.paineis["Pessoas"].itens["clientes"].clicked.emit()
    barra.botoes["Início"].click()
    barra.bt_venda.click()
    assert abertas == ["clientes", "dashboard", "pdv"]


def test_selecionar_acende_o_grupo_da_tela():
    barra = BarraMenu("Loja", ITENS_MENU, lambda c: True)
    barra.selecionar("ajuste_estoque")
    acesos = [r for r, b in barra.botoes.items() if b.isChecked()]
    assert acesos == ["Estoque"]
