"""Filtros de status com contagem grande nao podem alargar a tela de
Clientes alem do monitor (19/10: a janela passava da tela)."""

from telas import clientes


def test_filtros_com_contagem_grande_nao_alargam_a_tela(_qapp, monkeypatch):
    monkeypatch.setattr(clientes.Clientes, "carregar", lambda self: None)
    tela = clientes.Clientes()
    tela.show()
    _qapp.processEvents()
    largura_antes = tela.minimumSizeHint().width()

    for bt in tela.botoes_status.values():
        bt.setText(bt.property("rotulo") + "  1234")
    tela.lbl_contagem.setText("1234 clientes encontrados")
    _qapp.processEvents()

    assert tela.minimumSizeHint().width() == largura_antes
