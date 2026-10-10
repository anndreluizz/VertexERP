"""Finalizar com valor digitado e sem Enter: lanca e fecha a venda."""
from telas.pagamento import PagamentoWindow


def _tela_com_valor(total, forma, valor):
    tela = PagamentoWindow(total, [{"preco": total, "quantidade": 1}])
    tela.selecionar_forma(forma)
    tela.campo_valor.setText(valor)
    return tela


def test_valor_exato_sem_enter_finaliza(_qapp):
    tela = _tela_com_valor(50.0, "PIX", "50,00")

    assert tela.bt_confirmar.isEnabled()
    tela.confirmar()

    assert tela.result() == PagamentoWindow.Accepted
    assert tela.forma_pagamento == "PIX"


def test_dinheiro_com_troco_lanca_e_mostra_o_troco(_qapp):
    tela = _tela_com_valor(50.0, "DINHEIRO", "100,00")

    tela.confirmar()

    assert tela.result() != PagamentoWindow.Accepted
    assert tela.quitado() and tela.troco() == 50.0
    assert "Troco" in tela.lbl_aviso.text()

    tela.confirmar()
    assert tela.result() == PagamentoWindow.Accepted


def test_valor_parcial_lanca_e_avisa_quanto_falta(_qapp):
    tela = _tela_com_valor(50.0, "PIX", "30,00")

    tela.confirmar()

    assert tela.result() != PagamentoWindow.Accepted
    assert tela.pago() == 30.0
    assert "20,00" in tela.lbl_aviso.text()


def test_sem_forma_escolhida_finalizar_fica_desligado(_qapp):
    tela = PagamentoWindow(50.0, [{"preco": 50.0, "quantidade": 1}])

    assert not tela.bt_confirmar.isEnabled()
