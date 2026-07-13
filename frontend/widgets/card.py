from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class Card(QFrame):

    def __init__(self, titulo, valor):

        super().__init__()

        self.setMinimumHeight(130)

        self.setStyleSheet("""
            QFrame{
                background:white;
                border-radius:12px;
                border:1px solid #dcdcdc;
            }

            QLabel{
                border:none;
            }
        """)

        layout = QVBoxLayout(self)

        self.titulo = QLabel(titulo)
        self.titulo.setAlignment(Qt.AlignCenter)

        self.valor = QLabel(str(valor))
        self.valor.setAlignment(Qt.AlignCenter)

        self.titulo.setStyleSheet("""
            font-size:15px;
            color:gray;
        """)

        self.valor.setStyleSheet("""
            font-size:30px;
            font-weight:bold;
            color:#1565C0;
        """)

        layout.addStretch()
        layout.addWidget(self.titulo)
        layout.addWidget(self.valor)
        layout.addStretch()

    def atualizar(self, valor):

        self.valor.setText(str(valor))