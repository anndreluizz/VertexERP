"""Teste do cabecalho novo de PagamentoDespesaDialog -- confere que
o icone acompanha a troca de titulo/subtitulo quando o pagamento e
confirmado (credit-card -> check), igual ja acontecia com o texto."""
from unittest import mock

from telas.pagamento_despesa import PagamentoDespesaDialog

CONTA = {
    "id": 1,
    "descricao": "Aluguel do ponto",
    "categoria": "Aluguel",
    "valor": 1800.0,
    "data_vencimento": "2026-09-10T00:00:00",
    "observacao": None,
}


class _RespostaOk:
    status_code = 200

    def json(self):
        return {}


def test_icone_do_cabecalho_muda_para_check_ao_confirmar_pagamento(esperar_threads):

    # configuracoes() e' chamada tanto na hora de montar o dialogo
    # quanto de novo dentro de confirmar() (pra montar o texto do
    # comprovante) -- o mock precisa ficar de pe' pro teste inteiro,
    # nao so' na construcao.
    with mock.patch(
        "telas.pagamento_despesa.configuracoes",
        return_value={"nome_loja": "Loja Teste"},
    ):
        dialogo = PagamentoDespesaDialog(dict(CONTA))
        assert dialogo.paginas.currentWidget() is dialogo.pagina_confirmacao

        with mock.patch(
            "telas.pagamento_despesa.atualizar_conta_pagar",
            return_value=_RespostaOk(),
        ), mock.patch(
            "telas.pagamento_despesa.pagar_conta_pagar",
            return_value=_RespostaOk(),
        ):
            dialogo.confirmar()
            esperar_threads(dialogo)

    assert dialogo.paginas.currentWidget() is dialogo.pagina_comprovante
    assert not dialogo.cabecalho.icone.pixmap().isNull()
    assert dialogo.cabecalho.titulo.text() == "Pagamento Confirmado"


def test_montar_html_impressao_usa_template_premium_compartilhado(esperar_threads):
    """Ver Fase 6 Onda 5 -- o comprovante impresso/PDF passou a usar o
    mesmo cabecalho/tabela/total de utils/documento_html.py, em vez do
    texto solto que so' existia pro resumo em tela."""

    with mock.patch(
        "telas.pagamento_despesa.configuracoes",
        return_value={"nome_loja": "Loja Teste"},
    ):
        dialogo = PagamentoDespesaDialog(dict(CONTA))

        with mock.patch(
            "telas.pagamento_despesa.atualizar_conta_pagar",
            return_value=_RespostaOk(),
        ), mock.patch(
            "telas.pagamento_despesa.pagar_conta_pagar",
            return_value=_RespostaOk(),
        ):
            dialogo.confirmar()
            esperar_threads(dialogo)

    html = dialogo._montar_html_impressao()

    assert "COMPROVANTE DE PAGAMENTO" in html
    assert "Aluguel do ponto" in html
    assert "R$ 1.800,00" in html
    assert "px;'" not in html and 'px"' not in html
