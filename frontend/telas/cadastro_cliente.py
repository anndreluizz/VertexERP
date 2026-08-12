from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QHBoxLayout,
)


class CadastroClienteWindow(QDialog):

    def __init__(self, cliente=None):
        super().__init__()

        self.cliente = cliente

        self.setWindowTitle("Cadastro de Cliente")
        self.resize(700, 420)

        layout = QVBoxLayout(self)

        titulo = QLabel("CADASTRO DE CLIENTE")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            font-size:24px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        form = QFormLayout()

        self.nome = QLineEdit()
        self.cpf_cnpj = QLineEdit()
        self.telefone = QLineEdit()
        self.endereco = QLineEdit()
        self.ativo = QCheckBox("Cliente Ativo")
        self.ativo.setChecked(True)

        form.addRow("Nome", self.nome)
        form.addRow("CPF", self.cpf_cnpj)
        form.addRow("Telefone", self.telefone)
        form.addRow("Endereço", self.endereco)
        form.addRow("", self.ativo)

        layout.addLayout(form)

        botoes = QHBoxLayout()

        self.bt_cancelar = QPushButton("Cancelar")
        self.bt_salvar = QPushButton("Salvar")

        botoes.addStretch()
        botoes.addWidget(self.bt_cancelar)
        botoes.addWidget(self.bt_salvar)

        layout.addLayout(botoes)

        self.bt_cancelar.clicked.connect(self.reject)
        self.bt_salvar.clicked.connect(self.accept)

        if cliente:
            self.nome.setText(cliente["nome"])
            self.cpf_cnpj.setText(cliente.get("cpf_cnpj", ""))
            self.telefone.setText(cliente.get("telefone", ""))
            self.endereco.setText(cliente.get("endereco") or "")
            self.ativo.setChecked(cliente.get("ativo", True))

    @property
    def dados(self):
        return {
            "nome": self.nome.text(),
            "cpf_cnpj": self.cpf_cnpj.text(),
            "telefone": self.telefone.text(),
            "endereco": self.endereco.text(),
            "ativo": self.ativo.isChecked(),
        }