"""Depois de pagamento/compra no fiado, a ficha oferece mandar um
obrigado no WhatsApp com o saldo que ficou."""
from unittest import mock

from PySide6.QtWidgets import QMessageBox

from telas.ficha_cliente import FichaClienteDialog


def _ficha(telefone="(97) 90000-0001"):
    ficha = FichaClienteDialog.__new__(FichaClienteDialog)
    ficha.cliente = {"id": 1, "nome": "JOSE AZEVEDO", "telefone": telefone}
    ficha._enviar_texto_whatsapp = mock.Mock()
    return ficha


def _oferecer(ficha, saldo, resposta=QMessageBox.Yes):
    with mock.patch("telas.ficha_cliente.QMessageBox.question", return_value=resposta), \
         mock.patch("telas.ficha_cliente.saldo_cliente", return_value=saldo), \
         mock.patch("telas.ficha_cliente.api.configuracoes", return_value={"nome_loja": "3.L.A VARIEDADES"}):
        ficha._oferecer_agradecimento("Muito obrigado pelo seu pagamento de R$ 150,00!")


def test_manda_obrigado_com_saldo_restante():
    ficha = _ficha()
    _oferecer(ficha, 300.96)
    texto = ficha._enviar_texto_whatsapp.call_args[0][0]
    assert "pagamento de R$ 150,00" in texto
    assert "Saldo restante da sua conta: R$ 300,96" in texto
    assert "3.L.A VARIEDADES" in texto


def test_quitado_e_sem_telefone_e_nao():
    ficha = _ficha()
    _oferecer(ficha, 0)
    assert "quitada" in ficha._enviar_texto_whatsapp.call_args[0][0]

    sem_tel = _ficha(telefone=None)
    _oferecer(sem_tel, 10)
    sem_tel._enviar_texto_whatsapp.assert_not_called()

    recusou = _ficha()
    _oferecer(recusou, 10, QMessageBox.No)
    recusou._enviar_texto_whatsapp.assert_not_called()


def test_menu_agradece_o_ultimo_pagamento_sem_perguntar():
    ficha = _ficha()
    ficha._movimentos = [
        ({"tipo": "PAGAMENTO", "valor": 150.0}, 300.96),
        ({"tipo": "COMPRA", "valor": 450.96}, 450.96),
    ]
    with mock.patch("telas.ficha_cliente.QMessageBox.question") as pergunta, \
         mock.patch("telas.ficha_cliente.saldo_cliente", return_value=300.96), \
         mock.patch("telas.ficha_cliente.api.configuracoes", return_value={}):
        ficha.enviar_agradecimento_whatsapp()
    pergunta.assert_not_called()
    assert "pagamento de R$ 150,00" in ficha._enviar_texto_whatsapp.call_args[0][0]


def test_compra_so_agradece_sem_valor_nem_saldo():
    ficha = _ficha()
    ficha._movimentos = [({"tipo": "COMPRA", "valor": 58.99}, 154.98)]
    with mock.patch("telas.ficha_cliente.saldo_cliente") as saldo, \
         mock.patch("telas.ficha_cliente.api.configuracoes", return_value={}):
        ficha.enviar_agradecimento_whatsapp()
    texto = ficha._enviar_texto_whatsapp.call_args[0][0]
    assert "Muito obrigado pela sua compra!" in texto
    assert "R$" not in texto
    saldo.assert_not_called()
