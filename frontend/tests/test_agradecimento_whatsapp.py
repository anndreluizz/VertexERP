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
