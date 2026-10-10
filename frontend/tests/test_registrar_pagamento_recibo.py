"""Teste do fluxo de confirmar() do RegistrarPagamentoDialog -- o
recibo de pagamento nao pode mais imprimir sozinho, so' se o usuario
escolher no aviso de pagamento registrado (que tambem tem o botao
'Agradecer no WhatsApp' quando o cliente tem telefone)."""
from unittest import mock

from PySide6.QtWidgets import QMessageBox

from telas.ficha_cliente import RegistrarPagamentoDialog


class _RespostaOk:
    status_code = 200

    def json(self):
        return {}


def _confirmar(esperar_threads, botao, telefone=None):
    """Registra o pagamento clicando no botao 'botao' do aviso; devolve
    (dialogo, mock do imprimir, textos dos botoes oferecidos)."""

    cliente = {"id": 1, "nome": "Marcos Silva", "telefone": telefone}
    dialogo = RegistrarPagamentoDialog(cliente, saldo_devedor=100.0)
    dialogo.valor.setText("50,00")
    oferecidos = []

    class _Caixa(QMessageBox):
        def exec(self):
            botoes = {b.text(): b for b in self.buttons()}
            oferecidos.extend(botoes)
            self._escolha = botoes[botao]

        def clickedButton(self):
            return self._escolha

    with mock.patch(
        "telas.ficha_cliente.registrar_pagamento", return_value=_RespostaOk()
    ), mock.patch("telas.ficha_cliente.QMessageBox", _Caixa), mock.patch.object(
        dialogo, "_imprimir_recibo_pagamento"
    ) as mock_imprimir:
        dialogo.confirmar()
        esperar_threads(dialogo)

    return dialogo, mock_imprimir, oferecidos


def test_nao_imprime_recibo_se_usuario_fechar(esperar_threads):
    dialogo, imprimir, oferecidos = _confirmar(esperar_threads, "Fechar")
    imprimir.assert_not_called()
    assert not dialogo.agradecer_whatsapp
    assert "Agradecer no WhatsApp" not in oferecidos  # sem telefone


def test_imprime_recibo_apenas_se_usuario_pedir(esperar_threads):
    _, imprimir, _ = _confirmar(esperar_threads, "Imprimir recibo")
    imprimir.assert_called_once()


def test_botao_agradecer_e_os_dois(esperar_threads):
    dialogo, imprimir, _ = _confirmar(esperar_threads, "Agradecer no WhatsApp", "(97) 90000-0001")
    assert dialogo.agradecer_whatsapp
    imprimir.assert_not_called()

    dialogo, imprimir, _ = _confirmar(esperar_threads, "Os dois", "(97) 90000-0001")
    assert dialogo.agradecer_whatsapp
    imprimir.assert_called_once()
