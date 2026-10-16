"""Smoke test do botao 'Imprimir Relatorio' do Centro Financeiro --
antes nao fazia nada (bug: nunca foi conectado a nenhum metodo, ver
Fase 6 Onda 5). Confere que agora monta um HTML de verdade, no mesmo
template premium compartilhado, e manda pra impressao."""
from unittest import mock

from telas.relatorios import Relatorios

RELATORIO = {
    "receita_total": {"atual": 199.8, "anterior": 0, "variacao_pct": None},
    "top_produtos": [
        {"produto": "Camiseta Azul", "quantidade": 2, "total": 99.8},
    ],
    "formas_pagamento": [
        {"forma_pagamento": "PIX", "quantidade": 1, "total": 99.8},
    ],
}


def _tela_minima():
    tela = Relatorios.__new__(Relatorios)
    tela._aba_atual = 0
    tela._ultimo_relatorio_financeiro = RELATORIO
    tela.combo_periodo = mock.Mock(currentText=mock.Mock(return_value="Este mês"))
    tela.combo_loja = mock.Mock(currentText=mock.Mock(return_value="Todas as lojas"))
    return tela


def test_imprimir_relatorio_financeiro_monta_html_premium_e_chama_imprimir():

    tela = _tela_minima()

    with mock.patch(
        "telas.relatorios.financeiro.configuracoes", return_value={"nome_loja": "Loja Teste"}
    ), mock.patch(
        "telas.relatorios.financeiro.comprovante_service.obter_logo_loja", return_value=None
    ), mock.patch(
        "telas.relatorios.financeiro.comprovante_service.imprimir"
    ) as mock_imprimir:
        tela.imprimir_relatorio_financeiro()

    mock_imprimir.assert_called_once()
    html, parent = mock_imprimir.call_args[0]

    assert parent is tela
    assert "RELATÓRIO FINANCEIRO" in html
    assert "Loja Teste" in html
    assert "Camiseta Azul" in html
    assert "PIX" in html
    assert "R$ 199,80" in html


def test_imprimir_relatorio_financeiro_nao_faz_nada_fora_da_aba_financeiro():

    tela = _tela_minima()
    tela._aba_atual = 1  # aba Caixa

    with mock.patch(
        "telas.relatorios.financeiro.comprovante_service.imprimir"
    ) as mock_imprimir:
        tela.imprimir_relatorio_financeiro()

    mock_imprimir.assert_not_called()
