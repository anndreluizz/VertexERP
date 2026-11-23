"""Cadastro de produto: secoes opcionais comecam fechadas, o cabecalho diz o
estado, ligar o interruptor abre, e o resumo avisa o que falta."""
import importlib
import pkgutil
from unittest import mock

import telas.cadastro_produto as pacote
from design import tokens
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


def test_secoes_opcionais_comecam_fechadas(_qapp, monkeypatch):
    tela = _tela(monkeypatch)
    for secao in (tela.secao_detalhes, tela.secao_promo, tela.secao_vitrine, tela.secao_kit):
        assert not secao._corpo.isVisible()
    tela.close()


def test_ligar_promocao_abre_e_resume(_qapp, monkeypatch):
    tela = _tela(monkeypatch)
    tela.preco_venda.setValue(100)
    tela.em_promocao_check.setChecked(True)
    assert tela.secao_promo._corpo.isVisible()
    assert "Falta o preço promocional" in tela.secao_promo._lbl_resumo.text()
    tela.preco_promocional.setValue(80)
    assert tela.secao_promo._lbl_resumo.text().startswith("Ligada: R$")
    tela.close()


def test_resumo_diz_o_que_falta(_qapp, monkeypatch):
    tela = _tela(monkeypatch)
    assert tela.lbl_faltam.text() == "Falta: nome e preço de venda."
    tela.nome.setText("MOCHILA")
    tela.preco_venda.setValue(129.9)
    assert tela.lbl_faltam.text() == "Pronto pra salvar."
    tela.preco_custo.setValue(74)
    tela.estoque.setValue(6)
    assert tela.lbl_resumo_valor_estoque.text() == "R$ 444,00"
    tela.close()


def test_salvar_vazio_pinta_de_vermelho_sem_caixa_de_mensagem(_qapp, monkeypatch):
    tela = _tela(monkeypatch)
    tela.accept = mock.Mock()
    tela.salvar()
    tela.accept.assert_not_called()
    assert tokens.ERRO.lower() in tela.nome.styleSheet().lower()
    assert tela.lbl_faltam.text() == "Informe o nome do produto."

    tela.nome.setText("MOCHILA")  # corrigiu: o vermelho sai sozinho
    assert tokens.ERRO.lower() not in tela.nome.styleSheet().lower()
    assert tela.lbl_faltam.text() == "Informe um preço de venda válido."

    tela.preco_venda.setValue(10)
    tela.salvar()
    tela.accept.assert_called_once()
    tela.close()


def test_data_da_promocao_invertida_abre_a_secao_e_avisa(_qapp, monkeypatch):
    from PySide6.QtCore import QDate
    tela = _tela(monkeypatch)
    tela.accept = mock.Mock()
    tela.nome.setText("MOCHILA")
    tela.preco_venda.setValue(100)
    tela.em_promocao_check.setChecked(True)
    tela.preco_promocional.setValue(80)
    tela.promocao_inicio.setDate(QDate(2026, 12, 10))
    tela.promocao_fim.setDate(QDate(2026, 12, 1))
    tela.secao_promo.abrir(False)
    tela.salvar()
    tela.accept.assert_not_called()
    assert tela.secao_promo._corpo.isVisible()
    assert "Válida de" in tela.lbl_faltam.text()
    tela.close()


def test_interruptor_alterna_com_clique(_qapp, monkeypatch):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    tela = _tela(monkeypatch)
    assert not tela.eh_kit_check.isChecked()
    QTest.mouseClick(tela.eh_kit_check, Qt.LeftButton, pos=QPoint(10, 10))
    assert tela.eh_kit_check.isChecked()
    tela.close()
