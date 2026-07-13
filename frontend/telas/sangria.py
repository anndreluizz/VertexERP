from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
)


class SangriaWindow(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Sangria")
        self.setFixedSize(420, 260)

        layout = QVBoxLayout(self)

        titulo = QLabel("SANGRIA")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            font-size:22px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        layout.addSpacing(15)

        layout.addWidget(QLabel("Valor"))

        self.valor = QDoubleSpinBox()

        self.valor.setMinimum(0.01)

        self.valor.setMaximum(99999999)

        self.valor.setDecimals(2)

        self.valor.setPrefix("R$ ")

        layout.addWidget(self.valor)

        layout.addSpacing(10)

        layout.addWidget(QLabel("Descrição"))

        self.descricao = QLineEdit()

        self.descricao.setPlaceholderText(
            "Motivo da sangria"
        )

        layout.addWidget(self.descricao)

        layout.addStretch()

        botoes = QHBoxLayout()

        self.bt_cancelar = QPushButton("Cancelar")
        self.bt_confirmar = QPushButton("Confirmar")
        self.valor.setFocus()

        self.bt_confirmar.setStyleSheet("""
            QPushButton{
                background:#C62828;
                color:white;
                font-weight:bold;
            }

            QPushButton:hover{
                background:#B71C1C;
            }
        """)

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