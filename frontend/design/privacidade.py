"""Modo "valores ocultos" -- o olhinho do cabeçalho troca todo valor em
dinheiro mostrado pelos cards (e pelos totais do Caixa) por "R$ ••••",
pra cliente no balcão não ver faturamento, gaveta, fiado etc.

Começa SEMPRE oculto quando o app abre (de propósito: é a tela que fica
virada pro balcão); quem quer ver clica no olho."""

import re
import weakref

from PySide6.QtCore import QObject, Signal


MASCARA = "R$ ••••"

# "R$ 1.234,50", "R$ -12,00", "-R$ 5,00" -- qualquer valor formatado
# por formatar_moeda dentro de um texto maior também é coberto
_RE_MOEDA = re.compile(r"-?R\$\s?-?[\d.]+(?:,\d+)?")


def mascarar(texto):
    return _RE_MOEDA.sub(MASCARA, texto or "")


class _Privacidade(QObject):

    mudou = Signal(bool)

    def __init__(self):
        super().__init__()
        self.ocultos = True
        self._rotulos = weakref.WeakKeyDictionary()

    def alternar(self):
        self.definir_ocultos(not self.ocultos)

    def definir_ocultos(self, ocultos):
        self.ocultos = ocultos
        for rotulo, texto in list(self._rotulos.items()):
            self._pintar(rotulo, texto)
        self.mudou.emit(ocultos)

    def definir_texto(self, rotulo, texto):
        """Usar no lugar de rotulo.setText(...) pra textos com valor em
        dinheiro: guarda o texto real e mostra a máscara se estiver
        oculto (e troca sozinho quando o olhinho é clicado)."""
        self._rotulos[rotulo] = texto
        self._pintar(rotulo, texto)

    def _pintar(self, rotulo, texto):
        try:
            rotulo.setText(mascarar(texto) if self.ocultos else texto)
        except RuntimeError:
            # o QLabel já foi destruído pelo Qt (tela fechada)
            self._rotulos.pop(rotulo, None)


privacidade = _Privacidade()
