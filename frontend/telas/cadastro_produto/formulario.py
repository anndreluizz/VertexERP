from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QAbstractSpinBox,
    QCheckBox,
    QDoubleSpinBox,
    QPushButton,
    QDateEdit,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
)


from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import (
    Card,
)


class Interruptor(QCheckBox):
    """QCheckBox desenhado como botão deslizante (mesma API: toggled,
    isChecked, setEnabled...), com o texto ao lado."""

    _LARG, _ALT = 40, 22

    def __init__(self, texto=""):
        super().__init__(texto)
        self.setCursor(Qt.PointingHandCursor)
        font = self.font()
        font.setPixelSize(tokens.TAMANHO_SM)
        font.setWeight(QFont.DemiBold)
        self.setFont(font)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def sizeHint(self):
        texto = self.fontMetrics().horizontalAdvance(self.text())
        return QSize(self._LARG + (10 + texto if self.text() else 0) + 2, 28)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(1.0 if self.isEnabled() else 0.5)

        topo = (self.height() - self._ALT) / 2
        trilho = QRectF(1, topo, self._LARG, self._ALT)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(tokens.SUCESSO if self.isChecked() else tokens.BORDA_FORTE))
        p.drawRoundedRect(trilho, self._ALT / 2, self._ALT / 2)

        bolinha = self._ALT - 6
        x = trilho.right() - bolinha - 3 if self.isChecked() else trilho.left() + 3
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QRectF(x, topo + 3, bolinha, bolinha))

        if self.hasFocus():
            p.setPen(QPen(QColor(tokens.PRIMARIA), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(trilho.adjusted(-2, -2, 2, 2), self._ALT / 2 + 2, self._ALT / 2 + 2)

        if self.text():
            p.setPen(QColor(tokens.TEXTO))
            p.setFont(self.font())
            p.drawText(
                QRectF(trilho.right() + 10, 0, self.width() - trilho.right() - 10, self.height()),
                Qt.AlignVCenter | Qt.AlignLeft, self.text(),
            )


class _CabecalhoClicavel(QFrame):
    """Linha de cabeçalho que abre/fecha a seção (mouse ou Espaço)."""

    clicado = Signal()

    def __init__(self):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)

    def mousePressEvent(self, event):
        self.clicado.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self.clicado.emit()
            return
        super().keyPressEvent(event)


class SecaoRecolhivel(Card):
    """Cartão opcional do cadastro: começa fechado e o cabeçalho já diz o
    estado ("Ligada: R$ 109,90"), então dá pra ver tudo sem rolar. O
    interruptor (um QCheckBox já existente) mora no cabeçalho; ligar abre."""

    def __init__(self, titulo, resumo, icone_nome, cor, interruptor=None):

        super().__init__()

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self._cabecalho = _CabecalhoClicavel()
        self._cabecalho.setStyleSheet("background:transparent; border:none;")
        linha = QHBoxLayout(self._cabecalho)
        linha.setContentsMargins(18, 14, 18, 14)
        linha.setSpacing(12)

        cor_rgb = QColor(cor)
        chip = QLabel()
        chip.setFixedSize(32, 32)
        chip.setAlignment(Qt.AlignCenter)
        chip.setStyleSheet(f"""
            background: rgba({cor_rgb.red()}, {cor_rgb.green()}, {cor_rgb.blue()}, 0.12);
            border-radius:{tokens.RADIUS_SM}px;
        """)
        chip.setPixmap(icone_pixmap(icone_nome, cor=cor, tamanho=16))

        texto = QVBoxLayout()
        texto.setSpacing(1)
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:800;
        """)
        self._lbl_resumo = QLabel(resumo)
        self._lbl_resumo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        texto.addWidget(lbl_titulo)
        texto.addWidget(self._lbl_resumo)

        self._seta = QLabel()
        self._seta.setStyleSheet("background:transparent;")

        linha.addWidget(chip)
        linha.addLayout(texto, 1)
        if interruptor is not None:
            linha.addWidget(interruptor)
        linha.addWidget(self._seta)
        raiz.addWidget(self._cabecalho)

        self._corpo = QWidget()
        self._corpo.setStyleSheet("background:transparent;")
        caixa = QVBoxLayout(self._corpo)
        caixa.setContentsMargins(20, 16, 20, 18)
        caixa.setSpacing(12)
        divisor = QFrame()
        divisor.setFixedHeight(1)
        divisor.setStyleSheet(f"background:{tokens.BORDA};")
        raiz.addWidget(divisor)
        raiz.addWidget(self._corpo)
        self._divisor = divisor

        # quem monta a seção encaixa os campos aqui
        self.corpo = caixa

        self._cabecalho.clicado.connect(lambda: self.abrir(not self._corpo.isVisible()))
        if interruptor is not None:
            interruptor.toggled.connect(lambda ligado: ligado and self.abrir(True))
        self.abrir(False)

    def abrir(self, aberta):
        self._corpo.setVisible(aberta)
        self._divisor.setVisible(aberta)
        self._seta.setPixmap(icone_pixmap(
            "chevron-down" if aberta else "chevron-right",
            cor=tokens.TEXTO_TERCIARIO, tamanho=18,
        ))

    def definir_resumo(self, texto):
        self._lbl_resumo.setText(texto)


class FormularioMixin:
    """Pecas do formulario: campos, linhas, cartoes de secao e estilos."""

    # ==========================================
    # PEÇAS DO FORMULÁRIO
    # ==========================================

    def _input(self, placeholder):
        campo = QLineEdit()
        campo.setPlaceholderText(placeholder)
        campo.setMinimumHeight(44)
        campo.setStyleSheet(self._estilo_input())
        return campo

    def _dinheiro(self):
        campo = QDoubleSpinBox()
        campo.setMaximum(999999.99)
        campo.setDecimals(2)
        campo.setPrefix("R$ ")
        campo.setButtonSymbols(QAbstractSpinBox.NoButtons)
        campo.setMinimumHeight(44)
        campo.setStyleSheet(self._estilo_input("QDoubleSpinBox"))
        return campo

    def _data(self, data):
        campo = QDateEdit()
        campo.setCalendarPopup(True)
        campo.setDisplayFormat("dd/MM/yyyy")
        campo.setDate(data)
        campo.setMinimumHeight(44)
        campo.setStyleSheet(self._estilo_input("QDateEdit"))
        return campo

    @staticmethod
    def _interruptor(texto, dica):
        """Botão deslizante dos cabeçalhos recolhíveis e do Destaque."""
        check = Interruptor(texto)
        check.setToolTip(dica)
        check.setAccessibleName(dica)
        return check

    def _botao_icone(self, icone_nome, dica, ao_clicar):
        botao = QPushButton()
        botao.setCursor(Qt.PointingHandCursor)
        botao.setFixedSize(44, 44)
        botao.setToolTip(dica)
        botao.setAccessibleName(dica)
        botao.setIcon(icone(icone_nome, cor=tokens.TEXTO_SECUNDARIO, tamanho=16))
        botao.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; border:1.5px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.PRIMARIA_CLARA}; border-color:{tokens.PRIMARIA}; }}
        """)
        botao.clicked.connect(ao_clicar)
        return botao

    @staticmethod
    def _linha(*widgets):
        """Campo + botões grudados na mesma linha (ex.: categoria + / ≡)."""
        linha = QWidget()
        linha.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(widgets[0], 1)
        for widget in widgets[1:]:
            layout.addWidget(widget)
        return linha

    def _campo(self, rotulo, widget, obrigatorio=False):
        bloco = QWidget()
        bloco.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(bloco)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._rotulo_campo(rotulo, obrigatorio))
        layout.addWidget(widget)
        return bloco

    def _linha_resumo(self, layout, rotulo):
        linha = QHBoxLayout()
        lbl = QLabel(rotulo)
        lbl.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        valor = QLabel("—")
        valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)
        linha.addWidget(lbl)
        linha.addStretch()
        linha.addWidget(valor)
        layout.addLayout(linha)
        return valor

    # ==========================================
    # HELPERS DE ESTILO
    # ==========================================

    def _construir_cartao_secao(self, titulo, subtitulo, icone_nome, cor):
        """Card com cabeçalho (ícone colorido + título + subtítulo) e um
        corpo (QVBoxLayout) pra quem chama encaixar os campos --
        mesma linguagem visual do SecaoCard usado no Dashboard, só que
        com subtítulo, que aqui é essencial pra explicar cada bloco."""

        card = Card()

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        cabecalho_secao = QHBoxLayout()
        cabecalho_secao.setSpacing(12)

        icone_secao = QLabel()
        icone_secao.setFixedSize(36, 36)
        icone_secao.setAlignment(Qt.AlignCenter)
        cor_rgb = QColor(cor)
        icone_secao.setStyleSheet(f"""
            background: rgba({cor_rgb.red()}, {cor_rgb.green()}, {cor_rgb.blue()}, 0.12);
            border-radius:{tokens.RADIUS_SM}px;
        """)
        icone_secao.setPixmap(icone_pixmap(icone_nome, cor=cor, tamanho=17))

        col_titulo_secao = QVBoxLayout()
        col_titulo_secao.setSpacing(1)

        titulo_lbl = QLabel(titulo)
        titulo_lbl.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:800;
        """)

        subtitulo_lbl = QLabel(subtitulo)
        subtitulo_lbl.setWordWrap(True)
        subtitulo_lbl.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_titulo_secao.addWidget(titulo_lbl)
        col_titulo_secao.addWidget(subtitulo_lbl)

        cabecalho_secao.addWidget(icone_secao)
        cabecalho_secao.addLayout(col_titulo_secao, 1)

        layout.addLayout(cabecalho_secao)

        corpo_secao = QVBoxLayout()
        corpo_secao.setSpacing(12)
        layout.addLayout(corpo_secao)

        return card, corpo_secao

    def _rotulo_campo(self, texto, obrigatorio=False):

        sufixo = f' <span style="color:{tokens.ERRO};">*</span>' if obrigatorio else ""

        lbl = QLabel(f"{texto}{sufixo}")
        lbl.setTextFormat(Qt.RichText)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; color:{tokens.TEXTO_SECUNDARIO};
        """)
        return lbl

    def _estilo_input(self, widget="QLineEdit", erro=False):
        return f"""
            {widget} {{
                border: 1.5px solid {tokens.ERRO if erro else tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px;
                font-size: {tokens.TAMANHO_MD}px;
                color: {tokens.TEXTO};
                background: {tokens.ERRO_CLARO if erro else tokens.CARD};
            }}
            {widget}:focus {{
                border: 1.5px solid {tokens.PRIMARIA};
            }}
            {widget}:disabled {{
                background: {tokens.FUNDO};
                color: {tokens.TEXTO_TERCIARIO};
            }}
        """

    def _atualizar_estilo_favorito(self, marcado):

        self.favorito.setIcon(icone(
            "star-filled" if marcado else "star", cor="#FBBF24", tamanho=15,
        ))

        self.favorito.setStyleSheet(f"""
            QPushButton {{
                background: {'rgba(245, 158, 11, 0.18)' if marcado else 'transparent'};
                color: {'#FBBF24' if marcado else '#FFFFFF'};
                border: 1px solid {'#FBBF24' if marcado else 'rgba(255, 255, 255, 0.35)'};
                border-radius: {tokens.RADIUS_PILL}px;
                padding: 0 16px; font-weight: 700; font-size: {tokens.TAMANHO_SM}px;
            }}
            QPushButton:hover {{ background: rgba(255, 255, 255, 0.1); }}
        """)
