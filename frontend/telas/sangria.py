from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QLineEdit,
    QHBoxLayout,
    QPushButton,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.responsive import tamanho_fixo_seguro
from design.widgets import BotaoPerigo, BotaoSecundario


class SangriaWindow(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Sangria")
        tamanho_fixo_seguro(self, 420, 320)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(4)

        linha_cabecalho = QHBoxLayout()
        linha_cabecalho.setSpacing(14)

        icone_circulo = QLabel()
        icone_circulo.setFixedSize(48, 48)
        icone_circulo.setAlignment(Qt.AlignCenter)
        icone_circulo.setStyleSheet(f"""
            background:{tokens.ERRO_CLARO}; border-radius:24px;
        """)
        icone_circulo.setPixmap(icone_pixmap("arrow-down", cor=tokens.ERRO, tamanho=20))
        linha_cabecalho.addWidget(icone_circulo)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(2)

        titulo = QLabel("Sangria")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)

        subtitulo = QLabel("Retirada de dinheiro da gaveta")
        subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        linha_cabecalho.addLayout(col_titulo, 1)

        bt_fechar = QPushButton()
        bt_fechar.setFixedSize(30, 30)
        bt_fechar.setCursor(Qt.PointingHandCursor)
        bt_fechar.setAutoDefault(False)
        bt_fechar.setIcon(icone("x", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        bt_fechar.setToolTip("Fechar")
        bt_fechar.setAccessibleName("Fechar")
        bt_fechar.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        bt_fechar.clicked.connect(self.reject)
        linha_cabecalho.addWidget(bt_fechar, 0, Qt.AlignTop)

        layout.addLayout(linha_cabecalho)
        layout.addSpacing(14)

        lbl_valor = QLabel("VALOR")
        lbl_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)
        layout.addWidget(lbl_valor)

        self.valor = QDoubleSpinBox()
        self.valor.setMinimum(0)
        self.valor.setMaximum(99999999)
        self.valor.setDecimals(2)
        self.valor.setPrefix("R$ ")
        self.valor.setMinimumHeight(44)
        self.valor.setStyleSheet(f"""
            QDoubleSpinBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 10px; font-size: {tokens.TAMANHO_LG}px; font-weight: 700;
                color: {tokens.ERRO}; background: {tokens.CARD};
            }}
        """)

        layout.addWidget(self.valor)
        layout.addSpacing(12)

        lbl_descricao = QLabel("DESCRIÇÃO")
        lbl_descricao.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)
        layout.addWidget(lbl_descricao)

        self.descricao = QLineEdit()
        self.descricao.setPlaceholderText("Motivo da sangria")
        self.descricao.setMinimumHeight(44)
        self.descricao.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
            }}
            QLineEdit:focus {{ border: 1.5px solid {tokens.PRIMARIA}; }}
        """)

        layout.addWidget(self.descricao)

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        self.bt_cancelar = BotaoSecundario("Cancelar")
        self.bt_confirmar = BotaoPerigo("Confirmar Sangria")
        self.valor.setFocus()

        botoes.addWidget(self.bt_cancelar)
        botoes.addWidget(self.bt_confirmar)

        layout.addLayout(botoes)

        self.bt_cancelar.clicked.connect(
            self.reject
        )

        self.bt_confirmar.clicked.connect(
            self.confirmar
        )

    @property
    def dados(self):

        return {
            "tipo": "SANGRIA",
            "valor": float(self.valor.value()),
            "descricao": self.descricao.text(),
        }

    def confirmar(self):

        if self.valor.value() <= 0:
            QMessageBox.warning(
                self,
                "Aviso",
                "Informe um valor."
            )

            return

        if self.descricao.text().strip() == "":
            QMessageBox.warning(
                self,
                "Aviso",
                "Informe uma descrição."
            )

            return

        self.accept()
