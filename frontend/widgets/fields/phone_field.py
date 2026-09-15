"""Campo de telefone/WhatsApp com máscara automática -- 10 dígitos
vira fixo "(00) 0000-0000", 11 vira celular "(00) 00000-0000" (o 9º
dígito extra do celular), conforme o tanto que foi digitado."""

from design.widgets import CampoTexto

_MAX_DIGITOS = 11


def somente_digitos(texto):
    return "".join(c for c in texto if c.isdigit())


def formatar_telefone(digitos):

    d = digitos[:_MAX_DIGITOS]

    if not d:
        return ""

    texto = f"({d[:2]}"

    if len(d) > 2:
        texto += ") "
        fim_bloco = 7 if len(d) > 10 else 6
        texto += d[2:fim_bloco]
        if len(d) > fim_bloco:
            texto += f"-{d[fim_bloco:_MAX_DIGITOS]}"

    return texto


class PhoneField(CampoTexto):

    def __init__(self, placeholder="(00) 00000-0000", parent=None):
        super().__init__(placeholder, parent)
        self.setMaxLength(16)

        # textChanged (não textEdited) -- também reformata quando o
        # texto é setado por código (ex.: abrir um cadastro existente
        # pra editar), não só quando o usuário digita.
        self.textChanged.connect(self._reformatar)

    def _reformatar(self, texto):
        formatado = formatar_telefone(somente_digitos(texto))

        self.blockSignals(True)
        self.setText(formatado)
        self.blockSignals(False)
        self.setCursorPosition(len(formatado))

    @property
    def digitos(self):
        return somente_digitos(self.text())
