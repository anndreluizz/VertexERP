from PySide6.QtWidgets import QLabel

from design import tokens
from design.privacidade import mascarar, privacidade
from design.widgets import CardKPI


def test_mascarar_troca_so_os_valores_em_dinheiro():
    assert mascarar("R$ 1.234,50") == "R$ ••••"
    assert mascarar("-R$ 5,00") == "R$ ••••"
    assert mascarar("Vendas a prazo: R$ 12,00. Ok") == "Vendas a prazo: R$ ••••. Ok"
    assert mascarar("37") == "37"


def test_olhinho_esconde_e_mostra_card_e_rotulo():
    card = CardKPI("Faturamento", "dollar-sign", tokens.PRIMARIA)
    card.definir_valor("R$ 2.220,00")
    card_qtd = CardKPI("Pedidos", "file-text", tokens.PRIMARIA)
    card_qtd.definir_valor("12")
    rotulo = QLabel()
    privacidade.definir_texto(rotulo, "R$ 10,00")

    privacidade.alternar()
    assert privacidade.ocultos
    assert card.lbl_valor.text() == "R$ ••••"
    assert rotulo.text() == "R$ ••••"
    assert card_qtd.lbl_valor.text() == "12"

    privacidade.alternar()
    assert card.lbl_valor.text() == "R$ 2.220,00"
    assert rotulo.text() == "R$ 10,00"


def test_valor_novo_chegando_com_olho_fechado_ja_vem_mascarado():
    privacidade.definir_ocultos(True)
    card = CardKPI("Faturamento", "dollar-sign", tokens.PRIMARIA)
    card.definir_valor("R$ 99,00")
    assert card.lbl_valor.text() == "R$ ••••"
