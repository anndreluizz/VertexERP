from PySide6.QtCore import Qt, QDate

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QDateEdit,
    QPushButton,
    QMessageBox,
)


FORMAS_PAGAMENTO = [
    "DINHEIRO",
    "PIX",
    "CARTAO_CREDITO",
    "CARTAO_DEBITO",
    "BOLETO",
    "PRAZO",
]


class PagamentoCompraWindow(QDialog):

    def __init__(self):
        super().__init__()

        self.forma_pagamento = None

        self.data_vencimento = None

        self.setWindowTitle("Pagamento da Compra")

        self.resize(380, 220)

        layout = QVBoxLayout(self)

        titulo = QLabel("FORMA DE PAGAMENTO")

        titulo.setAlignment(Qt.AlignCenter)

        titulo.setStyleSheet("""
            font-size:18px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        self.combo_forma = QComboBox()

        self.combo_forma.addItems(FORMAS_PAGAMENTO)

        self.combo_forma.currentTextChanged.connect(
            self._alternar_vencimento
        )

        layout.addWidget(self.combo_forma)

        # ==========================================
        # VENCIMENTO (SÓ APARECE SE "PRAZO")
        # ==========================================

        self.label_vencimento = QLabel("Data de Vencimento")

        layout.addWidget(self.label_vencimento)

        self.vencimento = QDateEdit()

        self.vencimento.setCalendarPopup(True)

        self.vencimento.setDate(QDate.currentDate().addDays(30))

        layout.addWidget(self.vencimento)

        self.label_vencimento.setVisible(False)

        self.vencimento.setVisible(False)

        layout.addStretch()

        # ==========================================
        # BOTÕES
        # ==========================================

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

        botoes.addStretch()

        botoes.addWidget(self.bt_cancelar)

        botoes.addWidget(self.bt_confirmar)

        layout.addLayout(botoes)

        self.bt_cancelar.clicked.connect(self.reject)

        self.bt_confirmar.clicked.connect(self.confirmar)

    # ==========================================
    # MOSTRAR/OCULTAR CAMPO DE VENCIMENTO
    # ==========================================

    def _alternar_vencimento(self, forma):

        eh_prazo = (forma == "PRAZO")

        self.label_vencimento.setVisible(eh_prazo)

        self.vencimento.setVisible(eh_prazo)

    # ==========================================
    # CONFIRMAR
    # ==========================================

    def confirmar(self):

        forma = self.combo_forma.currentText()

        if forma == "PRAZO":

            if self.vencimento.date() <= QDate.currentDate():

                QMessageBox.warning(
                    self,
                    "Aviso",
                    "Informe uma data de vencimento futura."
                )

                return

            self.data_vencimento = (
                self.vencimento.date().toString("yyyy-MM-dd")
                + "T00:00:00"
            )

        else:

            self.data_vencimento = None

        self.forma_pagamento = forma

        self.accept()