from functools import lru_cache

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

from design.paths import caminho_asset


@lru_cache(maxsize=None)
def _pixmap(nome, cor, tamanho):

    caminho = caminho_asset("icons", f"{nome}.svg")

    with open(caminho, "r", encoding="utf-8") as arquivo:
        svg = arquivo.read()

    # os SVGs do Lucide usam stroke="currentColor" — precisa trocar
    # pela cor de verdade antes de renderizar, senao fica invisivel
    svg = svg.replace("currentColor", cor)

    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))

    pixmap = QPixmap(tamanho, tamanho)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return pixmap


def icone_pixmap(nome, cor="#1E293B", tamanho=20):
    return _pixmap(nome, cor, tamanho)


def icone(nome, cor="#1E293B", tamanho=20):
    return QIcon(_pixmap(nome, cor, tamanho))
