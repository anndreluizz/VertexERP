"""Navegação: barra do topo, abas das telas abertas e tela de módulos."""
from design.navegacao import CHAVE_INICIO, GRUPOS, SO_NA_BUSCA, BarraAbas, TelaModulos
from telas.principal import ITENS_MENU, PERMISSAO_TELA


def test_toda_tela_do_menu_esta_num_grupo():
    # sem grupo a tela fica sem bloco no Início (inalcancavel)
    nos_grupos = [c for _, chaves in GRUPOS for c in chaves]
    assert len(nos_grupos) == len(set(nos_grupos))
    assert set(nos_grupos) | SO_NA_BUSCA == {c for c, _, _ in ITENS_MENU}
    assert not set(nos_grupos) & SO_NA_BUSCA


def test_vendedor_nao_ve_blocos_de_admin():
    tela = TelaModulos("Ana Souza", ITENS_MENU, lambda c: c not in PERMISSAO_TELA)
    assert {"dashboard", "pdv", "clientes", "produtos"} <= set(tela.blocos)
    assert not set(tela.blocos) & set(PERMISSAO_TELA)


def test_bloco_e_barra_emitem_a_tela():
    tela = TelaModulos("Ana", ITENS_MENU, lambda c: True)
    barra = BarraAbas(lambda c: True)
    abertas = []
    tela.escolhido.connect(abertas.append)
    barra.nova_venda.connect(lambda: abertas.append("pdv"))

    tela.blocos["clientes"].clicado.emit("clientes")
    barra.bt_venda.click()
    assert abertas == ["clientes", "pdv"]


def test_vendedor_sem_pdv_nao_ve_nova_venda():
    assert not hasattr(BarraAbas(lambda c: c != "pdv"), "bt_venda")


def test_abas_abrir_nao_duplica_e_fechar_volta_pra_vizinha():
    abas = BarraAbas()
    abas.abrir(CHAVE_INICIO, "Início", "home")
    abas.abrir("pdv", "PDV", "shopping-cart")
    abas.abrir("produtos", "Produtos", "package")
    abas.abrir("pdv", "PDV", "shopping-cart")
    assert abas.abertas == [CHAVE_INICIO, "pdv", "produtos"]
    assert abas.atual == "pdv"

    assert abas.fechar("pdv") == CHAVE_INICIO
    assert abas.abertas == [CHAVE_INICIO, "produtos"]
    assert abas.atual == CHAVE_INICIO


def test_aba_inicio_nunca_fecha():
    abas = BarraAbas()
    abas.abrir(CHAVE_INICIO, "Início", "home")
    assert abas.fechar(CHAVE_INICIO) == CHAVE_INICIO
    assert abas.abertas == [CHAVE_INICIO]


def test_muitas_abas_nao_estouram_a_faixa():
    abas = BarraAbas(lambda c: True)
    abas.resize(900, 56)
    for i in range(20):
        abas.abrir(f"t{i}", f"Tela com nome bem comprido {i}", "home")
    abas.show()
    assert abas.abertas[-1] == "t19" and abas.atual == "t19"
    # o botao Nova venda continua visivel na direita, nao e' empurrado pra fora
    assert abas.bt_venda.geometry().right() <= abas.width()
