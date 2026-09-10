from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QApplication,
)

from design import tokens
from design.widgets import BotaoPrimario, BotaoSecundario
from services.api import verificar_codigo_2fa


class Verificar2FADialog(QDialog):
    """2o passo do login pra quem tem verificação em duas etapas
    ativada -- pede o código de 6 dígitos que chegou por e-mail (ver
    services/api.py: login() devolve um verificacao_id quando isso é
    necessário, em vez dos tokens direto)."""

    def __init__(self, verificacao_id, email, lembrar=False, parent=None):
        super().__init__(parent)

        self.verificacao_id = verificacao_id
        self.lembrar = lembrar

        self.setWindowTitle("Verificação em duas etapas")
        self.setFixedWidth(380)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        titulo = QLabel("Verificação em duas etapas")
        titulo.setWordWrap(True)
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            f"Mandamos um código de 6 dígitos para {email}. "
            "Digite ele abaixo pra continuar."
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(16)

        lbl_codigo = QLabel("CÓDIGO")
        lbl_codigo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.codigo = QLineEdit()
        self.codigo.setPlaceholderText("000000")
        self.codigo.setMaxLength(6)
        self.codigo.setAlignment(Qt.AlignCenter)
        self.codigo.setMinimumHeight(48)
        self.codigo.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: 22px; font-weight: 700;
                letter-spacing: 4px; color: {tokens.TEXTO}; background: {tokens.FUNDO};
            }}
            QLineEdit:focus {{ border: 1.5px solid {tokens.PRIMARIA}; }}
        """)
        self.codigo.returnPressed.connect(self.confirmar)

        layout.addWidget(lbl_codigo)
        layout.addSpacing(6)
        layout.addWidget(self.codigo)
        layout.addSpacing(20)

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.setMinimumHeight(44)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.clicked.connect(self.reject)

        bt_confirmar = BotaoPrimario("Confirmar")
        bt_confirmar.setMinimumHeight(44)
        bt_confirmar.setAutoDefault(False)
        bt_confirmar.clicked.connect(self.confirmar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(bt_confirmar)

        layout.addLayout(botoes)

        self.codigo.setFocus()

    def confirmar(self):

        codigo = self.codigo.text().strip()

        if not codigo:
            QMessageBox.warning(self, "Atenção", "Digite o código recebido por e-mail.")
            return

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        try:
            ok, erro = verificar_codigo_2fa(
                self.verificacao_id, codigo, lembrar=self.lembrar
            )
        finally:
            QApplication.restoreOverrideCursor()

        if ok:
            self.accept()
            return

        QMessageBox.warning(self, "Código inválido", erro)
        self.codigo.selectAll()
        self.codigo.setFocus()
