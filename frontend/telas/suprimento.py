from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QLineEdit,
    QHBoxLayout,
    QMessageBox,
)

from design import tokens
from design.responsive import tamanho_fixo_seguro
from design.widgets import BotaoSecundario, BotaoSucesso


class SuprimentoWindow(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Suprimento")
        tamanho_fixo_seguro(self, 420, 280)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(4)

        titulo = QLabel("Suprimento")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)

        subtitulo = QLabel("Reforço de dinheiro na gaveta")
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(18)

        lbl_valor = QLabel("VALOR")
        lbl_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)
        layout.addWidget(lbl_valor)

        self.valor = QDoubleSpinBox()
        self.valor.setMinimum(0.01)
        self.valor.setMaximum(99999999)
        self.valor.setDecimals(2)
        self.valor.setPrefix("R$ ")
        self.valor.setMinimumHeight(44)
        self.valor.setStyleSheet(f"""
            QDoubleSpinBox {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 10px; font-size: {tokens.TAMANHO_LG}px; font-weight: 700;
                color: {tokens.SECUNDARIA}; background: {tokens.CARD};
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
        self.descricao.setPlaceholderText("Motivo do suprimento")
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
        self.bt_confirmar = BotaoSucesso("Confirmar Suprimento")

        botoes.addWidget(self.bt_cancelar)
        botoes.addWidget(self.bt_confirmar)

        layout.addLayout(botoes)

        self.bt_cancelar.clicked.connect(
            self.reject
        )

        self.bt_confirmar.clicked.connect(
            self.confirmar
        )

        self.valor.setFocus()

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

    @property
    def dados(self):

        return {
            "tipo": "SUPRIMENTO",
            "valor": float(self.valor.value()),
            "descricao": self.descricao.text(),
        }
