"""Vertex 2.0: abas no topo + tela Início com os módulos (no lugar do
menu lateral)."""
from design.abas import ABA_FIXA, BarraAbas
from telas.modulos import GRUPOS, TelaModulos
from telas.principal import ITENS_MENU, PERMISSAO_TELA


def test_toda_tela_do_menu_tem_cartao_no_inicio():
    # sem cartao a tela fica inalcancavel (nao existe mais menu lateral)
    nos_grupos = [c for _, chaves in GRUPOS for c in chaves]
    assert len(nos_grupos) == len(set(nos_grupos))
    assert set(nos_grupos) == {c for c, _, _ in ITENS_MENU} - {ABA_FIXA}


def test_cartoes_respeitam_permissao_e_somem_grupo_vazio():
    vendedor = lambda chave: chave not in PERMISSAO_TELA
    tela = TelaModulos(ITENS_MENU, vendedor)
    assert "pdv" in tela.cartoes and "clientes" in tela.cartoes
    assert not set(tela.cartoes) & set(PERMISSAO_TELA)


def test_cartao_emite_a_tela():
    tela = TelaModulos(ITENS_MENU, lambda c: True)
    abertas = []
    tela.abrir.connect(abertas.append)
    tela.cartoes["clientes"].click()
    assert abertas == ["clientes"]


def test_abas_nao_duplicam_e_inicio_nao_fecha():
    barra = BarraAbas("Loja")
    emitidas = []
    barra.aba_selecionada.connect(emitidas.append)

    barra.abrir("inicio", "Início", "home")
    barra.abrir("pdv", "PDV", "shopping-cart")
    barra.abrir("clientes", "Clientes", "users")
    barra.abrir("pdv", "PDV", "shopping-cart")
    assert barra.chaves() == ["inicio", "pdv", "clientes"]
    assert barra.chave_atual() == "pdv"
    assert emitidas == []  # abrir() vem de quem ja' esta' exibindo a tela

    barra.fechar_indice(0)
    assert barra.chaves()[0] == "inicio"

    barra.fechar_atual()  # fecha o PDV: a vizinha vira a atual e e' exibida
    assert "pdv" not in barra.chaves()
    assert emitidas and emitidas[-1] == barra.chave_atual()


def test_ctrl_tab_da_a_volta():
    barra = BarraAbas("Loja")
    for chave in ("inicio", "pdv", "caixa"):
        barra.abrir(chave, chave, None)
    barra.proxima()
    assert barra.chave_atual() == "inicio"
    barra.proxima(-1)
    assert barra.chave_atual() == "caixa"
