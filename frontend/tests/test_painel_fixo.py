"""PainelFixo: o painel lateral acompanha a rolagem e nao some (17/11: rolando pra
baixo ele ia parar no fim da lista e nao voltava)."""
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from design.lista import PainelFixo


def test_painel_fica_na_vista_ao_descer_e_ao_subir(_qapp):
    rolagem = QScrollArea()
    rolagem.setWidgetResizable(True)
    pagina = QWidget()
    rolagem.setWidget(pagina)
    corpo = QHBoxLayout(pagina)
    lista = QWidget()
    lista.setFixedHeight(5000)
    corpo.addWidget(lista, 1)
    painel = QLabel("painel")
    painel.setFixedSize(200, 300)
    corpo.addWidget(PainelFixo(painel, rolagem))
    rolagem.resize(800, 600)
    rolagem.show()
    _qapp.processEvents()

    barra = rolagem.verticalScrollBar()
    for valor in (0, 1500, 3000, barra.maximum(), 1000, 0):
        barra.setValue(valor)
        _qapp.processEvents()
        y = painel.mapTo(rolagem.viewport(), QPoint(0, 0)).y()
        assert 0 <= y <= rolagem.viewport().height() - painel.height(), (valor, y)
