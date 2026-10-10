"""Teste do fluxo de confirmar() do RegistrarPagamentoDialog -- o
recibo de pagamento nao pode mais imprimir sozinho, so' se o usuario
confirmar quando perguntado (pedido direto: estava saindo automatico
demais, sem perguntar nada)."""
from unittest import mock

from PySide6.QtWidgets import QMessageBox

from telas.ficha_cliente import RegistrarPagamentoDialog

CLIENTE = {"id": 1, "nome": "Marcos Silva"}


class _RespostaOk:
    status_code = 200

    def json(self):
        return {}


def _dialogo():
    dialogo = RegistrarPagamentoDialog(CLIENTE, saldo_devedor=100.0)
    dialogo.valor.setText("50,00")
    return dialogo


def test_nao_imprime_recibo_se_usuario_recusar(esperar_threads):

    dialogo = _dialogo()

    with mock.patch(
        "telas.ficha_cliente.registrar_pagamento", return_value=_RespostaOk()
    ), mock.patch.object(
        QMessageBox, "question", return_value=QMessageBox.No
    ), mock.patch.object(
        dialogo, "_imprimir_recibo_pagamento"
    ) as mock_imprimir:
        dialogo.confirmar()
        esperar_threads(dialogo)

    mock_imprimir.assert_not_called()


def test_imprime_recibo_apenas_se_usuario_confirmar(esperar_threads):

    dialogo = _dialogo()

    with mock.patch(
        "telas.ficha_cliente.registrar_pagamento", return_value=_RespostaOk()
    ), mock.patch.object(
        QMessageBox, "question", return_value=QMessageBox.Yes
    ), mock.patch.object(
        dialogo, "_imprimir_recibo_pagamento"
    ) as mock_imprimir:
        dialogo.confirmar()
        esperar_threads(dialogo)

    mock_imprimir.assert_called_once()
