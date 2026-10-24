"""Item do menu lateral não pode ficar com o fundo de hover aceso depois
de deixar de ser o item ativo (bug: clicar em PDV, depois em Caixa, e o
PDV continuava destacado)."""
from unittest import mock

from PySide6.QtCore import QEvent, QPointF
from PySide6.QtGui import QEnterEvent

from design.sidebar import ItemMenuLateral


def test_hover_apaga_ao_sair_mesmo_com_item_ativo():
    with mock.patch("design.sidebar.movimento_reduzido", return_value=True):
        anterior = ItemMenuLateral("home", "PDV")
        novo = ItemMenuLateral("home", "Caixa")

        # passa o mouse no PDV, clica (vira o ativo) e tira o mouse
        anterior.enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))
        anterior.setChecked(True)
        anterior.leaveEvent(QEvent(QEvent.Leave))

        # clica em Caixa: o PDV deixa de ser o ativo
        novo.setChecked(True)
        anterior.setChecked(False)

        assert anterior.getOpacidadeFundo() == 0.0


def test_hover_anima_o_fundo_de_verdade():
    # opacidadeFundo era `property` do Python: o QPropertyAnimation nao
    # achava a propriedade e o hover nunca acendia (so' aviso no log do Qt)
    with mock.patch("design.sidebar.movimento_reduzido", return_value=False):
        item = ItemMenuLateral("home", "PDV")
        item.enterEvent(QEnterEvent(QPointF(), QPointF(), QPointF()))
        item._anim.setCurrentTime(item._anim.duration())

        assert item.getOpacidadeFundo() == 1.0
