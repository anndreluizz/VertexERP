"""Campo único de CPF/CNPJ, com máscara automática conforme a
quantidade de dígitos digitados -- até 11 vira CPF (000.000.000-00),
12 em diante vira CNPJ (00.000.000/0000-00). Pessoa física e jurídica
usam o mesmo campo no cadastro de cliente hoje, então o campo descobre
sozinho qual formato aplicar em vez de pedir pra escolher antes."""

from design.widgets import CampoTexto

_MAX_DIGITOS = 14


def somente_digitos(texto):
    return "".join(c for c in texto if c.isdigit())


def formatar_cpf_cnpj(digitos):

    d = digitos[:_MAX_DIGITOS]

    if len(d) <= 11:
        partes = [d[i:i + 3] for i in range(0, min(len(d), 9), 3)]
        texto = ".".join(partes)
        if len(d) > 9:
            texto += f"-{d[9:11]}"
        return texto

    texto = d[:2]
    if len(d) > 2:
        texto += f".{d[2:5]}"
    if len(d) > 5:
        texto += f".{d[5:8]}"
    if len(d) > 8:
        texto += f"/{d[8:12]}"
    if len(d) > 12:
        texto += f"-{d[12:14]}"
    return texto


class CpfCnpjField(CampoTexto):

    def __init__(self, placeholder="000.000.000-00", parent=None):
        super().__init__(placeholder, parent)
        self.setMaxLength(18)  # CNPJ formatado: 00.000.000/0000-00

        # textChanged (não textEdited) -- também reformata quando o
        # texto é setado por código (ex.: abrir um cadastro existente
        # pra editar), não só quando o usuário digita.
        self.textChanged.connect(self._reformatar)

    def _reformatar(self, texto):
        formatado = formatar_cpf_cnpj(somente_digitos(texto))

        # bloqueia o textChanged/textEdited durante o setText, senão
        # reentraria em _reformatar recursivamente pra cada chamada
        self.blockSignals(True)
        self.setText(formatado)
        self.blockSignals(False)
        self.setCursorPosition(len(formatado))

    @property
    def digitos(self):
        return somente_digitos(self.text())

    @property
    def valido(self):
        """Só confere a quantidade de dígitos (11 ou 14) -- não roda o
        algoritmo de dígito verificador oficial de CPF/CNPJ; já cobre
        o erro de digitação mais comum (número incompleto) sem
        reinventar validação de documento de verdade."""
        return len(self.digitos) in (11, 14)
