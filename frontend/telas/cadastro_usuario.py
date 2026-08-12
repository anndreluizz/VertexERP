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
    QMessageBox,
)


class CadastroUsuarioWindow(QDialog):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Novo Usuário")
        self.resize(420, 280)

        layout = QVBoxLayout(self)

        titulo = QLabel("NOVO USUÁRIO")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:20px; font-weight:bold;")
        layout.addWidget(titulo)

        form = QFormLayout()

        self.nome = QLineEdit()
        self.email = QLineEdit()
        self.senha = QLineEdit()
        self.senha.setEchoMode(QLineEdit.Password)
        self.admin = QCheckBox("Administrador")

        form.addRow("Nome", self.nome)
        form.addRow("E-mail", self.email)
        form.addRow("Senha", self.senha)
        form.addRow("", self.admin)

        layout.addLayout(form)

        botoes = QHBoxLayout()

        self.bt_cancelar = QPushButton("Cancelar")
        self.bt_salvar = QPushButton("Salvar")

        botoes.addStretch()
        botoes.addWidget(self.bt_cancelar)
        botoes.addWidget(self.bt_salvar)

        layout.addLayout(botoes)

        self.bt_cancelar.clicked.connect(self.reject)
        self.bt_salvar.clicked.connect(self.validar_e_salvar)

    def validar_e_salvar(self):

        if not self.nome.text().strip():
            QMessageBox.warning(self, "Atenção", "Informe o nome.")
            return

        if not self.email.text().strip():
            QMessageBox.warning(self, "Atenção", "Informe o e-mail.")
            return

        if not self.senha.text():
            QMessageBox.warning(self, "Atenção", "Informe a senha.")
            return

        self.accept()

    @property
    def dados(self):
        return {
            "nome": self.nome.text().strip(),
            "email": self.email.text().strip(),
            "senha": self.senha.text(),
            "admin": self.admin.isChecked(),
        }
