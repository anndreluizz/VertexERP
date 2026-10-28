"""Cartao "Vitrine virtual": destaque so' vale com o produto publicado."""
import importlib
import pkgutil
from unittest import mock

import telas.cadastro_produto as pacote
from telas.cadastro_produto import CadastroProdutoWindow


def _tela(monkeypatch):
    for m in pkgutil.iter_modules(pacote.__path__):
        modulo = importlib.import_module(f"telas.cadastro_produto.{m.name}")
        if hasattr(modulo, "rodar_em_thread"):
            monkeypatch.setattr(modulo, "rodar_em_thread", lambda *a, **k: None)
    with mock.patch("services.preferencias_service.carregar", return_value={}):
        return CadastroProdutoWindow()


def test_destaque_so_vai_junto_com_publicar(_qapp, monkeypatch):
    tela = _tela(monkeypatch)
    assert not tela.vitrine_destaque_check.isEnabled()

    tela.vitrine_publicar_check.setChecked(True)
    tela.vitrine_destaque_check.setChecked(True)
    assert tela.dados["vitrine_publicar"] is True
    assert tela.dados["vitrine_destaque"] is True

    tela.vitrine_publicar_check.setChecked(False)
    assert tela.dados["vitrine_publicar"] is False
    assert tela.dados["vitrine_destaque"] is False
