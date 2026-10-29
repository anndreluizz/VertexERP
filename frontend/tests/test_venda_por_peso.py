"""Produto em KG/L no PDV: peso digitado (janela ou "0,350*codigo"),
carrinho mostra "0,350 kg" e o subtotal arredonda no centavo."""
from unittest import mock

from telas.pdv import _separar_multiplicador
from test_pdv import _tela_pdv
from utils.formatacao import formatar_quantidade, subtotal_item

_PICANHA = {"id": 7, "codigo": "0007", "nome": "PICANHA", "preco": "39.90",
            "estoque": 12.5, "unidade": "KG"}
_CAMISETA = {"id": 8, "codigo": "0008", "nome": "CAMISETA", "preco": "50.00",
             "estoque": 10, "unidade": "UN"}


def test_multiplicador_aceita_peso_com_virgula():
    assert _separar_multiplicador("0,350*0007") == (0.35, "0007")
    assert _separar_multiplicador("1.5*0007") == (1.5, "0007")
    assert _separar_multiplicador("3*0007") == (3, "0007")


def test_formatar_quantidade_e_subtotal():
    assert formatar_quantidade(0.35, "KG") == "0,350 kg"
    assert formatar_quantidade(2, "UN") == "2"
    assert subtotal_item(39.90, 0.347) == 13.85  # 13,8453
    assert subtotal_item(1.00, 0.125) == 0.13  # meio pra cima, igual backend


def test_produto_por_kg_pede_peso_e_soma_no_carrinho():
    tela = _tela_pdv()
    with mock.patch("telas.pdv.pdv.pedir_peso", return_value=0.347):
        assert tela.adicionar_produto_ao_carrinho(_PICANHA, 1)
    assert tela.itens[0]["quantidade"] == 0.347
    assert tela.tabela.item(0, 3).text() == "0,347 kg"

    # "0,5*codigo" ja traz o peso: nao abre a janela
    with mock.patch("telas.pdv.pdv.pedir_peso") as janela:
        tela.adicionar_produto_ao_carrinho(_PICANHA, 0.5)
    janela.assert_not_called()
    assert tela.itens[0]["quantidade"] == 0.847


def test_cancelar_peso_nao_adiciona_e_un_recusa_virgula():
    tela = _tela_pdv()
    with mock.patch("telas.pdv.pdv.pedir_peso", return_value=None):
        assert not tela.adicionar_produto_ao_carrinho(_PICANHA, 1)
    assert not tela.adicionar_produto_ao_carrinho(_CAMISETA, 0.5)
    assert tela.itens == []


def test_peso_acima_do_estoque_e_recusado():
    tela = _tela_pdv()
    with mock.patch("telas.pdv.pdv.pedir_peso", return_value=13.0):
        assert not tela.adicionar_produto_ao_carrinho(_PICANHA, 1)


def test_janela_de_peso_devolve_valor_digitado():
    from PySide6.QtWidgets import QInputDialog
    from telas.pdv.comum import pedir_peso

    with mock.patch.object(QInputDialog, "exec", return_value=1), \
         mock.patch.object(QInputDialog, "doubleValue", return_value=0.3456):
        assert pedir_peso(None, _PICANHA) == 0.346
    with mock.patch.object(QInputDialog, "exec", return_value=0):
        assert pedir_peso(None, _PICANHA) is None
