"""Cadastro de produto: secoes opcionais comecam fechadas, o cabecalho diz o
estado, ligar o interruptor abre, e o resumo avisa o que falta."""
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
