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


def test_icone_do_cabecalho_muda_para_check_ao_confirmar_pagamento():

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

    assert dialogo.paginas.currentWidget() is dialogo.pagina_comprovante
    assert not dialogo.cabecalho.icone.pixmap().isNull()
    assert dialogo.cabecalho.titulo.text() == "Pagamento Confirmado"
