"""Ficha > WhatsApp > Enviar Agradecimento: obrigado pelo último
pagamento (com saldo restante) ou compra (só o obrigado)."""
from unittest import mock

from telas.ficha_cliente import FichaClienteDialog


def _ficha(*movimentos, telefone="(97) 90000-0001"):
    ficha = FichaClienteDialog.__new__(FichaClienteDialog)
    ficha.cliente = {"id": 1, "nome": "JOSE AZEVEDO", "telefone": telefone}
    ficha._movimentos = [(mov, 0) for mov in movimentos]  # mais novo primeiro
    ficha._enviar_texto_whatsapp = mock.Mock()
    return ficha


def _enviar(ficha, saldo=300.96, acao="agradecer_pagamento_whatsapp"):
    with mock.patch("telas.ficha_cliente.whatsapp.saldo_cliente", return_value=saldo), \
         mock.patch("telas.ficha_cliente.whatsapp.api.configuracoes", return_value={"nome_loja": "3.L.A VARIEDADES"}):
        getattr(ficha, acao)()
    return ficha._enviar_texto_whatsapp.call_args[0][0]


def test_pagamento_com_saldo_restante():
    # pagamento mesmo com uma compra mais nova depois
    texto = _enviar(_ficha({"tipo": "COMPRA", "valor": 5.0}, {"tipo": "PAGAMENTO", "valor": 150.0}))
    assert "pagamento de R$ 150,00" in texto
    assert "Saldo restante da sua conta: R$ 300,96" in texto
    assert "3.L.A VARIEDADES" in texto
    assert "quitada" in _enviar(_ficha({"tipo": "PAGAMENTO", "valor": 10.0}), saldo=0)


def test_compra_so_agradece_sem_valor_nem_saldo():
    texto = _enviar(_ficha({"tipo": "COMPRA", "valor": 58.99}), acao="agradecer_compra_whatsapp")
    assert "Muito obrigado pela sua compra!" in texto
    assert "R$" not in texto


def test_sem_telefone_avisa():
    ficha = _ficha({"tipo": "COMPRA", "valor": 10.0}, telefone=None)
    ficha.agradecer_compra_whatsapp()
    ficha._enviar_texto_whatsapp.assert_called_once()  # ele mostra "Sem telefone"
