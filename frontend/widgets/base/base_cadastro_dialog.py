from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)


class BaseCadastroDialog(QDialog):

    titulo = "Cadastro"
    largura = 700
    altura = 500
    texto_salvar = "Salvar"

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Vertex ERP")
        self.resize(self.largura, self.altura)
        self.setModal(True)

        self.layout = QVBoxLayout(self)

        self.criar_titulo()

        self.layout_campos = QVBoxLayout()
        self.layout.addLayout(self.layout_campos)

        self.layout.addStretch()

        self.criar_botoes()
        self.criar_campos()
        self.configurar_eventos()

    # ==========================================
    # TÍTULO
    # ==========================================
    def criar_titulo(self):
        titulo = QLabel(self.titulo)
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            font-size:24px;
            font-weight:bold;
            padding:10px;
        """)
        self.layout.addWidget(titulo)

    # ==========================================
    # BOTÕES
    # ==========================================
    def criar_botoes(self):
        botoes = QHBoxLayout()
        botoes.addStretch()

        self.bt_cancelar = QPushButton("Cancelar")
        self.bt_salvar = QPushButton(self.texto_salvar)

        self.bt_salvar.setStyleSheet("""
            QPushButton{
                background:#2E7D32;
                color:white;
                font-weight:bold;
                padding:8px 20px;
                border-radius:5px;
            }

            QPushButton:hover{
                background:#1B5E20;
            }
        """)

        botoes.addWidget(self.bt_cancelar)
        botoes.addWidget(self.bt_salvar)

        self.layout.addLayout(botoes)

    # ==========================================
    # EVENTOS
    # ==========================================
    def configurar_eventos(self):
        self.bt_cancelar.clicked.connect(self.reject)
        self.bt_salvar.clicked.connect(self.salvar)

    # ==========================================
    # SALVAR (com validação antes de fechar o diálogo)
    # ==========================================
    def salvar(self):
        if self.validar():
            self.accept()

    def validar(self):
        """
        Este método pode ser sobrescrito nas classes filhas
        para validar os campos antes de salvar. Deve retornar
        True se estiver tudo certo, ou False (exibindo algum
        aviso) para impedir o fechamento do diálogo.
        """
        return True

    # ==========================================
    # CAMPOS (implementado nas classes filhas)
    # ==========================================
    def criar_campos(self):
        """
        Este método será implementado nas classes filhas
        para adicionar os campos do formulário em
        self.layout_campos.
        """
        pass