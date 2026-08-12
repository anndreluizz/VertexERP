from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
)


class CadastroFornecedorWindow(QDialog):

    def __init__(self, fornecedor=None):
        super().__init__()

        self.fornecedor = fornecedor

        if fornecedor:
            self.setWindowTitle("Editar Fornecedor")
        else:
            self.setWindowTitle("Novo Fornecedor")

        self.resize(600, 400)

        layout = QVBoxLayout(self)

        titulo = QLabel("CADASTRO DE FORNECEDOR")

        titulo.setAlignment(Qt.AlignCenter)

        titulo.setStyleSheet("""
            font-size:22px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        formulario = QGridLayout()

        # ==========================================
        # Razão Social
        # ==========================================

        formulario.addWidget(QLabel("Razão Social"), 0, 0)

        self.razao_social = QLineEdit()

        formulario.addWidget(self.razao_social, 0, 1)

        # ==========================================
        # Nome Fantasia
        # ==========================================

        formulario.addWidget(QLabel("Nome Fantasia"), 1, 0)

        self.nome_fantasia = QLineEdit()

        formulario.addWidget(self.nome_fantasia, 1, 1)

        # ==========================================
        # CNPJ
        # ==========================================

        formulario.addWidget(QLabel("CNPJ"), 2, 0)

        self.cnpj = QLineEdit()

        formulario.addWidget(self.cnpj, 2, 1)

        # ==========================================
        # Email
        # ==========================================

        formulario.addWidget(QLabel("Email"), 3, 0)

        self.email = QLineEdit()

        formulario.addWidget(self.email, 3, 1)

        # ==========================================
        # Telefone
        # ==========================================

        formulario.addWidget(QLabel("Telefone"), 4, 0)

        self.telefone = QLineEdit()

        formulario.addWidget(self.telefone, 4, 1)

        # ==========================================
        # Cidade
        # ==========================================

        formulario.addWidget(QLabel("Cidade"), 5, 0)

        self.cidade = QLineEdit()

        formulario.addWidget(self.cidade, 5, 1)

        # ==========================================
        # Estado
        # ==========================================

        formulario.addWidget(QLabel("Estado"), 6, 0)

        self.estado = QLineEdit()

        self.estado.setMaxLength(2)

        formulario.addWidget(self.estado, 6, 1)

        layout.addLayout(formulario)

        layout.addStretch()

        # ==========================================
        # Botões
        # ==========================================

        botoes = QHBoxLayout()

        self.bt_cancelar = QPushButton("Cancelar")

        self.bt_salvar = QPushButton("Salvar")

        self.bt_salvar.setStyleSheet("""
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

        botoes.addWidget(self.bt_salvar)

        layout.addLayout(botoes)

        self.bt_cancelar.clicked.connect(
            self.reject
        )

        self.bt_salvar.clicked.connect(
            self.salvar
        )

        if self.fornecedor:
            self.preencher_campos()
            self.razao_social.setFocus()

    # ==========================================
    # PREENCHER CAMPOS (EDIÇÃO)
    # ==========================================

    def preencher_campos(self):

        if not self.fornecedor:
            return

        self.razao_social.setText(
            self.fornecedor["razao_social"]
        )

        self.nome_fantasia.setText(
            self.fornecedor.get("nome_fantasia") or ""
        )

        self.cnpj.setText(
            self.fornecedor["cnpj"]
        )

        self.email.setText(
            self.fornecedor.get("email") or ""
        )

        self.telefone.setText(
            self.fornecedor.get("telefone") or ""
        )

        self.cidade.setText(
            self.fornecedor.get("cidade") or ""
        )

        self.estado.setText(
            self.fornecedor.get("estado") or ""
        )

    # ==========================================
    # VALIDAR E SALVAR
    # ==========================================

    def salvar(self):

        if self.razao_social.text().strip() == "":
            QMessageBox.warning(
                self,
                "Aviso",
                "Informe a razão social."
            )
            self.razao_social.setFocus()
            return

        if self.cnpj.text().strip() == "":
            QMessageBox.warning(
                self,
                "Aviso",
                "Informe o CNPJ."
            )
            self.cnpj.setFocus()
            return

        self.accept()

    # ==========================================
    # DADOS
    # ==========================================

    @property
    def dados(self):

        dados = {

            "razao_social": self.razao_social.text(),

            "nome_fantasia": self.nome_fantasia.text() or None,

            "cnpj": self.cnpj.text(),

            "email": self.email.text() or None,

            "telefone": self.telefone.text() or None,

            "cidade": self.cidade.text() or None,

            "estado": self.estado.text() or None,
        }

        if self.fornecedor:
            dados["ativo"] = self.fornecedor.get("ativo", True)

        return dados