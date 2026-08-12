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


def fade_in(widget, duracao=220, ao_terminar=None):

    efeito = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(efeito)

    animacao = QPropertyAnimation(efeito, b"opacity", widget)
    animacao.setDuration(duracao)
    animacao.setStartValue(0.0)
    animacao.setEndValue(1.0)
    animacao.setEasingCurve(QEasingCurve.OutCubic)

    if ao_terminar:
        animacao.finished.connect(ao_terminar)

    widget._fade_in_anim = animacao
    animacao.start()

    return animacao


def slide_up(widget, distancia=16, duracao=260, ao_terminar=None):

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
