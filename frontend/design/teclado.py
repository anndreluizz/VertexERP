"""Acessibilidade global: nomes acessiveis, cards acionaveis por teclado e
botoes padrao do Qt em portugues. Chamado uma vez por design.theme."""

import os

import PySide6
from PySide6.QtCore import QEvent, QLibraryInfo, QObject, QTranslator, Qt
from PySide6.QtWidgets import QAbstractButton

from design import tokens


class _NomeAcessivel(QObject):
    """Botao so com icone costuma ter tooltip mas nao nome acessivel: ao
    aparecer na tela, copia o tooltip pro nome (leitores de tela leem o nome)."""

    def eventFilter(self, obj, evento):
        if evento.type() == QEvent.Show and isinstance(obj, QAbstractButton):
            if not obj.accessibleName() and not obj.text().strip() and obj.toolTip():
                obj.setAccessibleName(obj.toolTip())
        return False


class _TeclaAcao(QObject):
    """Enter/Espaco num card focado faz o mesmo que o clique."""

    def __init__(self, widget, acao):
        super().__init__(widget)
        self._acao = acao
        widget.installEventFilter(self)

    def eventFilter(self, obj, evento):
        if evento.type() == QEvent.KeyPress and evento.key() in (
            Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space
        ):
            self._acao()
            return True
        return False


def tornar_acionavel(widget, acao, nome, cor_anel=None):
    """Card clicavel que o Tab alcanca, com anel de foco e acao no Enter/Espaco."""
    widget.setFocusPolicy(Qt.StrongFocus)
    widget.setAccessibleName(nome)
    if not widget.objectName():
        widget.setObjectName(f"acionavel_{id(widget)}")
    cor = cor_anel or tokens.PRIMARIA
    widget.setStyleSheet(
        widget.styleSheet()
        + f"\nQFrame#{widget.objectName()}:focus {{ border: 2px solid {cor}; }}"
    )
    _TeclaAcao(widget, acao)


def instalar(app):
    app._filtro_nome_acessivel = _NomeAcessivel(app)
    app.installEventFilter(app._filtro_nome_acessivel)

    # Yes/No/Cancel/Save... em portugues (so ha traducao se o arquivo existir)
    traducao = QTranslator(app)
    pastas = [
        QLibraryInfo.path(QLibraryInfo.TranslationsPath),
        os.path.join(os.path.dirname(PySide6.__file__), "translations"),
    ]
    if any(traducao.load("qtbase_pt_BR", p) for p in pastas):
        app.installTranslator(traducao)
        app._traducao_qt = traducao
