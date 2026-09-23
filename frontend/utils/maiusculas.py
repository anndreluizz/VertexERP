"""Cadastro em MAIUSCULAS, padrao de ERP de loja -- o texto ja sai
maiusculo enquanto e' digitado (e colado), sem precisar de Caps Lock.

So' pra campos de nome/descricao curta. Nunca aplicar em e-mail, senha,
login, URL ou codigo: e-mail/senha mudam de sentido em maiusculas e
codigo de barras/CPF nao tem letra pra mudar."""

from PySide6.QtGui import QValidator


class ValidadorMaiusculas(QValidator):

    def validate(self, texto, posicao):
        return QValidator.Acceptable, texto.upper(), posicao


def forcar_maiusculas(*campos):
    """Aceita QLineEdit ou QComboBox editavel. O validador tambem pega
    texto colocado por codigo (ex.: ao abrir um cadastro antigo pra
    editar, "Mochila" aparece "MOCHILA" e e' salvo assim) -- os
    cadastros antigos so' mudam quando alguem abre e salva, nao ha'
    conversao em massa."""

    for campo in campos:

        edicao = campo.lineEdit() if hasattr(campo, "lineEdit") else campo

        if edicao is None:
            continue  # QComboBox nao editavel -- nao tem o que digitar

        edicao.setValidator(ValidadorMaiusculas(edicao))
