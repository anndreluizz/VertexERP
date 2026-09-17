"""Helpers de animação reutilizáveis. Mantidos propositalmente sutis —
o pedido era elegância, não efeito chamativo. Guarda referência às
animações/efeitos nos próprios widgets (setProperty) pra evitar que o
garbage collector do Python derrube o QPropertyAnimation no meio do
percurso, um bug clássico de animação Qt "que não anima nada"."""

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
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
