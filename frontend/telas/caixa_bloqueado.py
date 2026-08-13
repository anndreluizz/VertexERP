from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
)

from design import tokens
from design.icons import icone_pixmap
from design.responsive import tamanho_fixo_seguro
from design.widgets import BotaoSecundario, BotaoSucesso


class CaixaBloqueadoDialog(QDialog):

    def __init__(self, parent=None):

        super().__init__(parent)

        self.abrir_solicitado = False

        self.setWindowTitle("Caixa Fechado")
        tamanho_fixo_seguro(self, 400, 320)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 30, 32, 30)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignHCenter)

        icone = QLabel()
        icone.setFixedSize(56, 56)
        icone.setAlignment(Qt.AlignCenter)
        icone.setStyleSheet(f"""
            background:{tokens.ALERTA_CLARO};
            border-radius:28px;
        """)
        icone.setPixmap(icone_pixmap("lock", cor=tokens.ALERTA, tamanho=24))

        layout.addWidget(icone, alignment=Qt.AlignHCenter)
        layout.addSpacing(10)

        titulo = QLabel("O caixa precisa estar aberto")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setWordWrap(True)
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            "Para acessar o Frente de Caixa e registrar vendas, "
            "abra o caixa informando o troco inicial."
        )
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO};
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(16)

        bt_abrir = BotaoSucesso("Abrir Caixa")
        bt_abrir.setMinimumHeight(46)
        bt_abrir.clicked.connect(self.abrir)

        bt_cancelar = BotaoSecundario("Agora não")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.clicked.connect(self.reject)

        layout.addWidget(bt_abrir)
        layout.addWidget(bt_cancelar)

    def abrir(self):
        self.abrir_solicitado = True
        self.accept()
