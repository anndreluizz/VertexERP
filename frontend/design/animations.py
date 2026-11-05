"""Helpers de animação reutilizáveis. Mantidos propositalmente sutis —
o pedido era elegância, não efeito chamativo. Guarda referência às
animações/efeitos nos próprios widgets (setProperty) pra evitar que o
garbage collector do Python derrube o QPropertyAnimation no meio do
percurso, um bug clássico de animação Qt "que não anima nada"."""

import re

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QVariantAnimation,
    Qt,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect

from utils.acessibilidade import movimento_reduzido


def fade_in(widget, duracao=220, ao_terminar=None):

    # respeita "Mostrar animacoes" do Windows -- pula direto pro
    # estado final (widget totalmente visivel) em vez de animar
    if movimento_reduzido():
        if ao_terminar:
            ao_terminar()
        return None

    efeito = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(efeito)

    animacao = QPropertyAnimation(efeito, b"opacity", widget)
    animacao.setDuration(duracao)
    animacao.setStartValue(0.0)
    animacao.setEndValue(1.0)
    animacao.setEasingCurve(QEasingCurve.OutCubic)

    def _ao_completar():
        # tira o efeito assim que a animação termina. Parado em
        # opacity=1.0 ele é um no-op visualmente, mas deixá-lo preso
        # no widget pra sempre força todo repaint dali em diante a
        # passar pelo caminho de composição em cache do efeito (em vez
        # de pintura direta) -- confirmado que isso corrompe a
        # renderização de certos widgets (texto em negrito no tema
        # escuro, visto no cabeçalho do PDV) numa captura offscreen.
        # O "is efeito" evita apagar um efeito diferente que algo mais
        # já tenha colocado no widget nesse meio-tempo.
        if widget.graphicsEffect() is efeito:
            widget.setGraphicsEffect(None)
        if ao_terminar:
            ao_terminar()

    animacao.finished.connect(_ao_completar)

    widget._fade_in_anim = animacao
    animacao.start()

    return animacao


def slide_up(widget, distancia=16, duracao=260, ao_terminar=None):

    if movimento_reduzido():
        if ao_terminar:
            ao_terminar()
        return None

    pos_final = widget.pos()
    pos_inicial = QPoint(pos_final.x(), pos_final.y() + distancia)

    widget.move(pos_inicial)

    animacao = QPropertyAnimation(widget, b"pos", widget)
    animacao.setDuration(duracao)
    animacao.setStartValue(pos_inicial)
    animacao.setEndValue(pos_final)
    animacao.setEasingCurve(QEasingCurve.OutCubic)

    if ao_terminar:
        animacao.finished.connect(ao_terminar)

    widget._slide_anim = animacao
    animacao.start()

    return animacao


# "R$ 1.284,50", "-R$ 5,00", "23", "14 produtos", "12,5%" -- so' textos
# que SAO um numero (com prefixo R$ e/ou sufixo curto); datas, "—" e
# frases ficam de fora e so' trocam o texto.
_RE_NUMERO_KPI = re.compile(r"^(-?R\$\s?-?|-?)(\d{1,3}(?:\.\d{3})*|\d+)(,\d+)?(\s*[%\w ]{0,20})$")


def _formatar_br(valor, casas):
    texto = f"{valor:,.{casas}f}"  # 1,284.50
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def contar(rotulo, texto, duracao=650):
    """Mostra `texto` no QLabel contando o numero de 0 ate' o valor
    (efeito de painel). Passa sempre por privacidade.definir_texto, entao
    com o olhinho fechado continua "R$ ••••". Devolve False quando o texto
    nao e' um numero (ai' so' troca o texto, sem animar)."""
    from design.privacidade import privacidade

    anterior = getattr(rotulo, "_contar_anim", None)
    if anterior is not None:
        anterior.stop()

    achado = _RE_NUMERO_KPI.match((texto or "").strip())
    if not achado or movimento_reduzido():
        privacidade.definir_texto(rotulo, texto)
        return False

    prefixo, inteiro, decimal, sufixo = achado.groups()
    casas = len(decimal) - 1 if decimal else 0
    alvo = float(inteiro.replace(".", "") + ("." + decimal[1:] if decimal else ""))
    if alvo == 0:
        privacidade.definir_texto(rotulo, texto)
        return False

    animacao = QVariantAnimation(rotulo)
    animacao.setDuration(duracao)
    animacao.setStartValue(0.0)
    animacao.setEndValue(alvo)
    animacao.setEasingCurve(QEasingCurve.OutCubic)
    animacao.valueChanged.connect(
        lambda v: privacidade.definir_texto(rotulo, f"{prefixo}{_formatar_br(v, casas)}{sufixo}")
    )
    # termina no texto original exato (sem arredondamento da animacao)
    animacao.finished.connect(lambda: privacidade.definir_texto(rotulo, texto))
    rotulo._contar_anim = animacao
    animacao.start()
    return True
