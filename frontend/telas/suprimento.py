from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
)


class SuprimentoWindow(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Suprimento")

        self.setFixedSize(420, 260)

        layout = QVBoxLayout(self)

        titulo = QLabel("SUPRIMENTO")

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
            "Motivo do suprimento"
        )

        layout.addWidget(self.descricao)

        layout.addStretch()

        botoes = QHBoxLayout()

        self.bt_cancelar = QPushButton("Cancelar")

        self.bt_confirmar = QPushButton("Confirmar")

        self.bt_confirmar.setStyleSheet("""
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