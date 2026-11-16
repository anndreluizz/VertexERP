"""Seletor: QComboBox com a aparência de filtro (pílula) e o menu novo.

É um QComboBox de verdade (mesma API: addItem, currentData, activated...), só que
o popup é um menu com marca no item escolhido e, em listas longas, busca.

- Seletor()            -> pílula de filtro (azul quando fora da opção padrão)
- Seletor(campo=True)  -> campo de formulário: mantém o estilo que a tela aplicar,
                          só troca o popup
- combo editável       -> não mexe (a pessoa digita), usa o popup nativo
"""

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QComboBox, QFrame, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from design import tokens
from design.icons import icone

_COM_BUSCA = 8  # a partir de quantos itens o menu ganha a caixa de busca


class _Menu(QFrame):
    """Popup: busca (opcional) + lista rolável de itens."""

    def __init__(self, seletor):
        super().__init__(seletor, Qt.Popup)
        self.setObjectName("menuSeletor")
        self.setStyleSheet(
            f"QFrame#menuSeletor {{ background:{tokens.CARD}; border:1px solid {tokens.BORDA_FORTE};"
            f" border-radius:{tokens.RADIUS_MD}px; }}"
        )
        self.setMinimumWidth(max(seletor.width(), 220))
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(8, 8, 8, 8)
        raiz.setSpacing(6)

        self._busca = None
        if seletor.count() >= _COM_BUSCA:
            self._busca = QLineEdit()
            self._busca.setPlaceholderText("Buscar…")
            self._busca.setFixedHeight(34)
            self._busca.addAction(icone("search", tokens.TEXTO_TERCIARIO, 16), QLineEdit.LeadingPosition)
            self._busca.setStyleSheet(
                f"QLineEdit {{ border:1.5px solid {tokens.BORDA_CAMPO}; border-radius:{tokens.RADIUS_SM}px;"
                f" padding:0 10px; background:{tokens.CARD}; color:{tokens.TEXTO};"
                f" font-size:{tokens.TAMANHO_BASE}px; }}"
                f"QLineEdit:focus {{ border-color:{tokens.PRIMARIA}; }}"
            )
            self._busca.textChanged.connect(self._filtrar)
            raiz.addWidget(self._busca)

        lista = QWidget()
        lista.setStyleSheet("background:transparent;")
        col = QVBoxLayout(lista)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        self._botoes = []
        for i in range(seletor.count()):
            texto = seletor.itemText(i)
            ativo = i == seletor.currentIndex()
            bt = QPushButton(texto)
            bt.setFixedHeight(34)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setIcon(icone("check", tokens.PRIMARIA if ativo else tokens.CARD, 16))
            bt.setStyleSheet(
                f"QPushButton {{ text-align:left; border:none; border-radius:{tokens.RADIUS_SM}px;"
                f" padding:0 10px; font-size:{tokens.TAMANHO_BASE}px;"
                f" font-weight:{700 if ativo else 500}; color:{tokens.PRIMARIA if ativo else tokens.TEXTO};"
                f" background:{tokens.PRIMARIA_CLARA if ativo else 'transparent'}; }}"
                f"QPushButton:hover {{ background:{tokens.FUNDO}; }}"
            )
            bt.clicked.connect(lambda _=False, k=i: self._escolher(seletor, k))
            col.addWidget(bt)
            self._botoes.append(bt)
        col.addStretch()

        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        rolagem.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        rolagem.setWidget(lista)
        rolagem.setMaximumHeight(320)
        rolagem.setMinimumHeight(min(320, 36 * seletor.count()))
        raiz.addWidget(rolagem)

    def _filtrar(self, texto):
        texto = texto.strip().lower()
        for bt in self._botoes:
            bt.setVisible(texto in bt.text().lower())

    def _escolher(self, seletor, indice):
        self.close()
        mudou = indice != seletor.currentIndex()
        seletor.setCurrentIndex(indice)
        seletor.activated.emit(indice)  # como o popup nativo
        if mudou:
            seletor.update()

    def showEvent(self, evento):
        super().showEvent(evento)
        if self._busca is not None:
            self._busca.setFocus()


class Seletor(QComboBox):

    def __init__(self, parent=None, campo=False):
        super().__init__(parent)
        self._filtro = not campo
        self._padrao = None  # índice "sem filtro", capturado na 1ª exibição
        self._interno = False
        if self._filtro:
            self.setCursor(Qt.PointingHandCursor)
            self.setFixedHeight(36)
            self._pintar()
            self.currentIndexChanged.connect(lambda _=0: self._pintar())

    # a tela pode mandar estilo/altura de combo antigo: no modo filtro vale o da pílula
    def setStyleSheet(self, estilo):
        if self._filtro and not self._interno:
            return
        super().setStyleSheet(estilo)

    def setMinimumHeight(self, altura):
        if not self._filtro:
            super().setMinimumHeight(altura)

    def _ativo(self):
        return self._padrao is not None and self.currentIndex() != self._padrao

    def _pintar(self):
        if not self._filtro:
            return
        ativo = self._ativo()
        self._interno = True
        super().setStyleSheet(
            f"QComboBox {{ padding:0 34px 0 14px; border-radius:18px; font-weight:600;"
            f" font-size:{tokens.TAMANHO_SM}px; background:{tokens.PRIMARIA_CLARA if ativo else tokens.CARD};"
            f" color:{tokens.PRIMARIA if ativo else tokens.TEXTO_SECUNDARIO};"
            f" border:1px solid {tokens.PRIMARIA if ativo else tokens.BORDA_FORTE}; }}"
            f"QComboBox:hover {{ background:{tokens.PRIMARIA_CLARA if ativo else tokens.FUNDO}; }}"
            f"QComboBox::drop-down {{ width:0; border:none; }}"
            f"QComboBox::down-arrow {{ image:none; width:0; }}"
        )
        self._interno = False

    def showEvent(self, evento):
        super().showEvent(evento)
        if self._filtro and self._padrao is None:
            self._padrao = self.currentIndex()
            self._pintar()

    def paintEvent(self, evento):
        super().paintEvent(evento)
        if not self._filtro:
            return
        cor = tokens.PRIMARIA if self._ativo() else tokens.TEXTO_TERCIARIO
        pm = icone("chevron-down", cor, 16).pixmap(16, 16)
        p = QPainter(self)
        p.drawPixmap(self.width() - 28, (self.height() - 16) // 2, pm)
        p.end()

    def showPopup(self):
        if self.isEditable() or self.count() == 0:
            return super().showPopup()
        menu = _Menu(self)
        menu.move(self.mapToGlobal(QPoint(0, self.height() + 6)))
        menu.show()
