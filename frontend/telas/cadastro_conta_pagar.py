from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QDateEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QMessageBox,
    QDialogButtonBox,
)

from telas.pesquisa_fornecedor import PesquisaFornecedorWindow


class CadastroContaPagarWindow(QDialog):

    def __init__(self, conta=None):
        super().__init__()

        self.conta = conta
        self.fornecedor_id = None
        self.fornecedor_nome = None

        self.setWindowTitle(
            "Editar Conta a Pagar" if conta else "Nova Conta a Pagar"
        )

        self.resize(500, 320)

        layout = QVBoxLayout(self)

        titulo = QLabel("CONTA A PAGAR")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            font-size:20px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        formulario = QGridLayout()

        # ==========================================
        # Fornecedor (opcional — conta avulsa se vazio)
        # ==========================================

        formulario.addWidget(QLabel("Fornecedor"), 0, 0)

        fornecedor_layout = QHBoxLayout()

        self.fornecedor = QLineEdit()
        self.fornecedor.setReadOnly(True)
        self.fornecedor.setPlaceholderText(
            "Nenhum — conta avulsa (aluguel, luz, etc.)"
        )

        self.bt_fornecedor = QPushButton("Selecionar...")
        self.bt_fornecedor.clicked.connect(self.selecionar_fornecedor)

        self.bt_limpar_fornecedor = QPushButton("✕")
        self.bt_limpar_fornecedor.setToolTip("Remover fornecedor")
        self.bt_limpar_fornecedor.setMaximumWidth(30)
        self.bt_limpar_fornecedor.clicked.connect(self.limpar_fornecedor)

        fornecedor_layout.addWidget(self.fornecedor)
        fornecedor_layout.addWidget(self.bt_fornecedor)
        fornecedor_layout.addWidget(self.bt_limpar_fornecedor)

        formulario.addLayout(fornecedor_layout, 0, 1)

        # ==========================================
        # Valor
        # ==========================================

        formulario.addWidget(QLabel("Valor"), 1, 0)

        self.valor = QDoubleSpinBox()
        self.valor.setMaximum(999999.99)
        self.valor.setDecimals(2)
        self.valor.setPrefix("R$ ")

        formulario.addWidget(self.valor, 1, 1)

        # ==========================================
        # Vencimento
        # ==========================================

        formulario.addWidget(QLabel("Vencimento"), 2, 0)

        self.vencimento = QDateEdit()
        self.vencimento.setCalendarPopup(True)
        self.vencimento.setDate(QDate.currentDate().addDays(30))

        formulario.addWidget(self.vencimento, 2, 1)

        # ==========================================
        # Número do Boleto
        # ==========================================

        formulario.addWidget(QLabel("Número do Boleto"), 3, 0)

        self.numero_boleto = QLineEdit()
        self.numero_boleto.setPlaceholderText(
            "Linha digitável / código de barras (opcional)"
        )

        formulario.addWidget(self.numero_boleto, 3, 1)

        # ==========================================
        # Observação
        # ==========================================

        formulario.addWidget(QLabel("Observação"), 4, 0)

        self.observacao = QLineEdit()

        formulario.addWidget(self.observacao, 4, 1)

        layout.addLayout(formulario)

        layout.addStretch()

        # ==========================================
        # Botões
        # ==========================================

        botoes = QDialogButtonBox(
            QDialogButtonBox.Cancel | QDialogButtonBox.Save
        )

        botoes.accepted.connect(self.salvar)
        botoes.rejected.connect(self.reject)

        layout.addWidget(botoes)

        if self.conta:
            self.preencher_campos()

    # ==========================================
    # SELECIONAR FORNECEDOR
    # ==========================================

    def selecionar_fornecedor(self):

        tela = PesquisaFornecedorWindow()

        if tela.exec() != QDialog.Accepted:
            return

        self.fornecedor_id = tela.fornecedor["id"]
        self.fornecedor_nome = tela.fornecedor["razao_social"]

        self.fornecedor.setText(self.fornecedor_nome)

    # ==========================================
    # LIMPAR FORNECEDOR (CONTA AVULSA)
    # ==========================================

    def limpar_fornecedor(self):

        self.fornecedor_id = None
        self.fornecedor_nome = None
        self.fornecedor.clear()

    # ==========================================
    # PREENCHER CAMPOS (EDIÇÃO)
    # ==========================================

    def preencher_campos(self):

        if self.conta.get("fornecedor_id"):
            self.fornecedor_id = self.conta["fornecedor_id"]
            self.fornecedor.setText(
                self.conta.get("fornecedor_nome") or ""
            )

        self.valor.setValue(float(self.conta["valor"]))

        data = QDate.fromString(
            self.conta["data_vencimento"][:10], "yyyy-MM-dd"
        )
        self.vencimento.setDate(data)

        self.numero_boleto.setText(
            self.conta.get("numero_boleto") or ""
        )
        self.observacao.setText(
            self.conta.get("observacao") or ""
        )

    # ==========================================
    # VALIDAR E SALVAR
    # ==========================================

    def salvar(self):

        if self.valor.value() <= 0:
            QMessageBox.warning(
                self, "Aviso", "Informe um valor maior que zero."
            )
            return

        self.accept()

    # ==========================================
    # DADOS
    # ==========================================

    @property
    def dados(self):

        return {
            "fornecedor_id": self.fornecedor_id,
            "data_vencimento": (
                self.vencimento.date().toString("yyyy-MM-dd")
                + "T00:00:00"
            ),
            "valor": float(self.valor.value()),
            "numero_boleto": self.numero_boleto.text() or None,
            "observacao": self.observacao.text() or None,
        }
