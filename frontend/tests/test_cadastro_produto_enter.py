"""Novo Produto: Enter anda pelos campos do cartao "Principal" na ordem
codigo -> nome -> categoria -> preco -> custo -> estoque, e no estoque
cadastra."""
import importlib
import pkgutil
from unittest import mock

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

import telas.cadastro_produto as pacote
from telas.cadastro_produto import CadastroProdutoWindow


def _tela(monkeypatch):
    for m in pkgutil.iter_modules(pacote.__path__):
        modulo = importlib.import_module(f"telas.cadastro_produto.{m.name}")
        if hasattr(modulo, "rodar_em_thread"):
            monkeypatch.setattr(modulo, "rodar_em_thread", lambda *a, **k: None)
    with mock.patch("services.preferencias_service.carregar", return_value={}):
        tela = CadastroProdutoWindow()
    tela.show()
    return tela


def _enter(tela):
    tela.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Return, Qt.NoModifier))
    QApplication.processEvents()


def _focado(tela, campo):
    foco = QApplication.focusWidget()
    while foco is not None and foco is not campo:
        foco = foco.parentWidget()
    return foco is campo


def test_enter_segue_a_ordem_do_cartao_principal_e_cadastra_no_estoque(_qapp, monkeypatch):
    tela = _tela(monkeypatch)
    tela.salvar = mock.Mock()
    tela.codigo_barras.setFocus()
    QApplication.processEvents()

    for campo in (tela.nome, tela.categoria, tela.preco_venda, tela.preco_custo, tela.estoque):
        _enter(tela)
        assert _focado(tela, campo)

    tela.salvar.assert_not_called()
    _enter(tela)
    tela.salvar.assert_called_once()
    tela.close()
