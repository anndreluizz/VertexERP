"""Validações de formato usadas em formulários -- nenhum cadastro do
sistema checava o formato do e-mail digitado (só se não estava vazio),
o que só ia dar erro lá na frente, na hora de enviar comprovante/SMTP,
sem nunca ter sido sinalizado pra quem cadastrou."""

import re

# Checagem de formato simples (não verifica se o domínio existe de
# verdade nem bate um RFC 5322 completo) -- só o suficiente pra pegar
# erro de digitação óbvio, tipo "nome@gmail" ou "nome@@gmail.com" ou
# "nomegmail.com", sem ser rígido demais e recusar e-mail real.
_REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def email_valido(texto):
    """True pra vazio/None também -- quem chama decide se o campo é
    obrigatório; essa função só valida o FORMATO de quem preencheu
    algo."""

    texto = (texto or "").strip()

    if not texto:
        return True

    return bool(_REGEX_EMAIL.match(texto))
