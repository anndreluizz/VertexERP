from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QPushButton,
    QHBoxLayout,
)


class AbrirCaixaWindow(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Abrir Caixa")
        self.setFixedSize(400, 220)

        layout = QVBoxLayout(self)

        titulo = QLabel("ABRIR CAIXA")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            font-size:22px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        layout.addSpacing(15)

        lbl = QLabel("Saldo Inicial")

        self.valor = QDoubleSpinBox()

        self.valor.setMaximum(99999999)

        self.valor.setDecimals(2)

        self.valor.setPrefix("R$ ")

        self.valor.setValue(0)

        layout.addWidget(lbl)
        layout.addWidget(self.valor)

        layout.addStretch()

        botoes = QHBoxLayout()

        self.bt_cancelar = QPushButton("Cancelar")
        self.bt_abrir = QPushButton("Abrir Caixa")

        self.bt_abrir.setStyleSheet("""
            QPushButton{
                background:#2E7D32;
                color:white;
                font-weight:bold;
            }

            QPushButton:hover{
                background:#1B5E20;
            }
        """)

        botoes.addWidget(self.bt_cancelar)
        botoes.addWidget(self.bt_abrir)

        layout.addLayout(botoes)

        self.bt_cancelar.clicked.connect(self.reject)
        self.bt_abrir.clicked.connect(self.accept)

    @property
    def saldo(self):
        return float(self.valor.value())