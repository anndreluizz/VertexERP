"""ProtegeAlteracoes: avisa so quando a pessoa mexeu, e salvar nao avisa."""
from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox, QVBoxLayout

from design.alteracoes import ProtegeAlteracoes

ALVO = "widgets.dialogs.message_dialog._executar"


class _Dlg(ProtegeAlteracoes, QDialog):
    def __init__(self):
        super().__init__()
        self.campo = QLineEdit()
        QVBoxLayout(self).addWidget(self.campo)
        self.campo.setText("carga inicial")  # carga programatica nao conta


def _novo():
    QApplication.instance() or QApplication([])
    d = _Dlg()
    d.show()
    return d


def test_sem_mexer_fecha_sem_perguntar():
    d = _novo()
    with mock.patch(ALVO) as pergunta:
        d.reject()
    pergunta.assert_not_called()
    assert not d.isVisible()


def test_mexeu_e_recusou_continua_aberto():
    d = _novo()
    QTest.keyClicks(d.campo, "x")
    with mock.patch(ALVO, return_value=QMessageBox.No) as pergunta:
        d.reject()
    pergunta.assert_called_once()
    assert d.isVisible()
    d._alteracoes = False  # close() tambem chama reject()
    d.close()


def test_mexeu_e_confirmou_sai():
    d = _novo()
    QTest.keyClicks(d.campo, "x")
    with mock.patch(ALVO, return_value=QMessageBox.Yes):
        d.reject()
    assert not d.isVisible()


def test_salvar_nao_pergunta():
    d = _novo()
    QTest.keyClicks(d.campo, "x")
    with mock.patch(ALVO) as pergunta:
        d.accept()
    pergunta.assert_not_called()
    assert not d.isVisible()
