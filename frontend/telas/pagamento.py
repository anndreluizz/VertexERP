from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QRadioButton,
    QLineEdit,
    QButtonGroup,
    QMessageBox,
)


class PagamentoWindow(QDialog):

    def __init__(self, total):
        super().__init__()

        self.total = total
        self.forma_pagamento = "DINHEIRO"

        self.setWindowTitle("Finalizar Venda")
        self.setFixedSize(500, 420)

        layout = QVBoxLayout(self)

        titulo = QLabel("FINALIZAR VENDA")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            font-size:22px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        # ===========================
        # TOTAL
        # ===========================

        self.lbl_total = QLabel(
            f"TOTAL: R$ {total:.2f}"
        )

        self.lbl_total.setAlignment(Qt.AlignCenter)

        self.lbl_total.setStyleSheet("""
            font-size:30px;
            color:#1565C0;
            font-weight:bold;
        """)

        layout.addWidget(self.lbl_total)

        # ===========================
        # FORMAS DE PAGAMENTO
        # ===========================

        self.dinheiro = QRadioButton("Dinheiro")
        self.pix = QRadioButton("PIX")
        self.cartao = QRadioButton("Cartão")
        self.prazo = QRadioButton("Prazo")

        self.dinheiro.setChecked(True)

        grupo = QButtonGroup(self)

        grupo.addButton(self.dinheiro)
        grupo.addButton(self.pix)
        grupo.addButton(self.cartao)
        grupo.addButton(self.prazo)

        layout.addWidget(self.dinheiro)
        layout.addWidget(self.pix)
        layout.addWidget(self.cartao)
        layout.addWidget(self.prazo)

        # ===========================
        # VALOR RECEBIDO
        # ===========================

        layout.addSpacing(20)

        self.recebido = QLineEdit()
        self.recebido.setPlaceholderText("Valor Recebido")

        layout.addWidget(self.recebido)

        self.troco = QLabel("Troco: R$ 0,00")

        self.troco.setStyleSheet("""
            font-size:18px;
            font-weight:bold;
        """)

        layout.addWidget(self.troco)

        self.recebido.textChanged.connect(
            self.calcular_troco
        )

        # ===========================
        # BOTÕES
        # ===========================

        botoes = QHBoxLayout()

        self.bt_cancelar = QPushButton("Cancelar")
        self.bt_confirmar = QPushButton("Confirmar Venda")

        botoes.addWidget(self.bt_cancelar)
        botoes.addWidget(self.bt_confirmar)

        layout.addStretch()
        layout.addLayout(botoes)

        self.bt_cancelar.clicked.connect(self.reject)
        self.bt_confirmar.clicked.connect(self.confirmar)

    # ======================================

    def calcular_troco(self):

        try:
            recebido = float(
                self.recebido.text().replace(",", ".")
            )
        except:
            recebido = 0

        troco = recebido - self.total

        if troco < 0:
            troco = 0

        self.troco.setText(
            f"Troco: R$ {troco:.2f}"
        )

    # ======================================

    def confirmar(self):

        if self.dinheiro.isChecked():

            self.forma_pagamento = "DINHEIRO"

            try:
                recebido = float(
                    self.recebido.text().replace(",", ".")
                )
            except:
                QMessageBox.warning(
                    self,
                    "Atenção",
                    "Informe o valor recebido."
                )
                return

            if recebido < self.total:

                QMessageBox.warning(
                    self,
                    "Atenção",
                    "O valor recebido é menor que o total."
                )
                return

        elif self.pix.isChecked():

            self.forma_pagamento = "PIX"

        elif self.cartao.isChecked():

            self.forma_pagamento = "CREDITO"

        else:

            self.forma_pagamento = "PRAZO"

        self.accept()