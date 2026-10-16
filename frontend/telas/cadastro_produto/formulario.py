from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
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

    def _estilo_input(self, widget="QLineEdit"):
        return f"""
            {widget} {{
                border: 1.5px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px;
                font-size: {tokens.TAMANHO_MD}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
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
            "star-filled" if marcado else "star", cor=tokens.ALERTA, tamanho=15,
        ))

        self.favorito.setStyleSheet(f"""
            QPushButton {{
                background: {tokens.ALERTA_CLARO if marcado else tokens.CARD};
                color: {tokens.ALERTA_TEXTO};
                border: 1.5px solid {tokens.ALERTA if marcado else tokens.BORDA};
                border-radius: {tokens.RADIUS_PILL}px;
                padding: 0 16px; font-weight: 700; font-size: {tokens.TAMANHO_SM}px;
            }}
            QPushButton:hover {{ background: {tokens.ALERTA_CLARO}; }}
        """)
