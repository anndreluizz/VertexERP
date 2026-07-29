from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
)


class CaixaBloqueadoDialog(QDialog):

    def __init__(self, parent=None):

        super().__init__(parent)

        self.abrir_solicitado = False

        self.setWindowTitle("Caixa Fechado")
        self.setFixedSize(400, 320)
        self.setStyleSheet("background:white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 30, 32, 30)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignHCenter)

        icone = QLabel("🔒")
        icone.setFixedSize(56, 56)
        icone.setAlignment(Qt.AlignCenter)
        icone.setStyleSheet("""
            background:#FFF3E0;
            color:#E65100;
            font-size:24px;
            border-radius:28px;
        """)

        layout.addWidget(icone, alignment=Qt.AlignHCenter)
        layout.addSpacing(10)

        titulo = QLabel("O caixa precisa estar aberto")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setWordWrap(True)
        titulo.setStyleSheet(
            "background:transparent; font-size:17px; "
            "font-weight:bold; color:#202225;"
        )

        subtitulo = QLabel(
            "Para acessar o Frente de Caixa e registrar vendas, "
            "abra o caixa informando o troco inicial."
        )
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(
            "background:transparent; font-size:12px; color:gray;"
        )

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(16)

        bt_abrir = QPushButton("Abrir Caixa")
        bt_abrir.setMinimumHeight(46)
        bt_abrir.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                color:white;
                font-weight:bold;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
        """)
        bt_abrir.clicked.connect(self.abrir)

        bt_cancelar = QPushButton("Agora não")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setStyleSheet("""
            QPushButton {
                background:white;
                color:#202225;
                border:1px solid #cccccc;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#f4f5f7;
            }
        """)
        bt_cancelar.clicked.connect(self.reject)

        layout.addWidget(bt_abrir)
        layout.addWidget(bt_cancelar)

    def abrir(self):
        self.abrir_solicitado = True
        self.accept()
