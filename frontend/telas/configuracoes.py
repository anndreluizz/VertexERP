from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QTabWidget,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QFileDialog,
    QDialog,
    QAbstractItemView,
    QHeaderView,
)

IMPRESSAO_COMPROVANTE_LABEL = {
    "perguntar": "Perguntar a cada venda",
    "sempre": "Sempre imprimir",
    "nunca": "Nunca imprimir",
}

from telas.cadastro_usuario import CadastroUsuarioWindow
from services.configuracao_service import (
    buscar_configuracoes,
    atualizar_configuracoes,
    enviar_logo,
    buscar_logo_bytes,
)
from services.user_service import (
    listar_usuarios,
    cadastrar_usuario,
    definir_admin,
    definir_ativo,
)


class Configuracoes(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        titulo = QLabel("CONFIGURAÇÕES")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:24px; font-weight:bold;")
        layout.addWidget(titulo)

        abas = QTabWidget()
        abas.addTab(self._montar_aba_loja(), "🏬 Dados da Loja")
        abas.addTab(self._montar_aba_pix(), "💠 PIX")
        abas.addTab(self._montar_aba_usuarios(), "👥 Usuários")

        layout.addWidget(abas)

        self.carregar()

    # ==========================================
    # ABA: DADOS DA LOJA
    # ==========================================

    def _montar_aba_loja(self):
        aba = QWidget()
        layout = QVBoxLayout(aba)

        logo_layout = QHBoxLayout()

        self.logo_preview = QLabel("Sem logo")
        self.logo_preview.setFixedSize(120, 120)
        self.logo_preview.setAlignment(Qt.AlignCenter)
        self.logo_preview.setStyleSheet("""
            border: 1px solid #444;
            border-radius: 8px;
            background: #2b2b2b;
        """)

        bt_logo = QPushButton("Selecionar Logo...")
        bt_logo.clicked.connect(self.selecionar_logo)

        logo_layout.addWidget(self.logo_preview)
        logo_layout.addWidget(bt_logo)
        logo_layout.addStretch()

        layout.addLayout(logo_layout)

        form = QFormLayout()

        self.nome_loja = QLineEdit()
        self.cnpj_cpf = QLineEdit()
        self.endereco = QLineEdit()
        self.telefone = QLineEdit()

        form.addRow("Nome da Loja", self.nome_loja)
        form.addRow("CNPJ/CPF", self.cnpj_cpf)
        form.addRow("Endereço", self.endereco)
        form.addRow("Telefone", self.telefone)

        self.impressao_comprovante = QComboBox()
        for valor, rotulo in IMPRESSAO_COMPROVANTE_LABEL.items():
            self.impressao_comprovante.addItem(rotulo, valor)

        form.addRow(
            "Comprovante da Venda (PDV)", self.impressao_comprovante
        )

        layout.addLayout(form)

        bt_salvar = QPushButton("Salvar Dados da Loja")
        bt_salvar.setStyleSheet(self._estilo_botao_salvar())
        bt_salvar.clicked.connect(self.salvar_loja)
        layout.addWidget(bt_salvar)

        layout.addStretch()

        return aba

    # ==========================================
    # ABA: PIX
    # ==========================================

    def _montar_aba_pix(self):
        aba = QWidget()
        layout = QVBoxLayout(aba)

        form = QFormLayout()

        self.pix_chave = QLineEdit()
        self.pix_chave.setPlaceholderText("CPF/CNPJ, e-mail, telefone ou chave aleatória")

        self.pix_nome = QLineEdit()
        self.pix_cidade = QLineEdit()

        form.addRow("Chave PIX", self.pix_chave)
        form.addRow("Nome do Recebedor", self.pix_nome)
        form.addRow("Cidade", self.pix_cidade)

        layout.addLayout(form)

        bt_salvar = QPushButton("Salvar PIX")
        bt_salvar.setStyleSheet(self._estilo_botao_salvar())
        bt_salvar.clicked.connect(self.salvar_pix)
        layout.addWidget(bt_salvar)

        layout.addStretch()

        return aba

    # ==========================================
    # ABA: USUÁRIOS
    # ==========================================

    def _montar_aba_usuarios(self):
        aba = QWidget()
        layout = QVBoxLayout(aba)

        toolbar = QHBoxLayout()

        bt_novo = QPushButton("+ Novo Usuário")
        bt_novo.setStyleSheet(self._estilo_botao_salvar())
        bt_novo.clicked.connect(self.novo_usuario)

        toolbar.addWidget(bt_novo)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        self.tabela_usuarios = QTableWidget()
        self.tabela_usuarios.setColumnCount(5)
        self.tabela_usuarios.setHorizontalHeaderLabels(
            ["Nome", "E-mail", "Admin", "Status", "Ações"]
        )
        self.tabela_usuarios.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela_usuarios.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela_usuarios.verticalHeader().setVisible(False)
        self.tabela_usuarios.setAlternatingRowColors(True)

        layout.addWidget(self.tabela_usuarios)

        return aba

    # ==========================================
    # ESTILO COMPARTILHADO
    # ==========================================

    def _estilo_botao_salvar(self):
        return """
            QPushButton {
                background: #2E7D32;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background: #1B5E20;
            }
        """

    # ==========================================
    # CARREGAR TUDO
    # ==========================================

    def carregar(self):
        dados = buscar_configuracoes()

        self.nome_loja.setText(dados.get("nome_loja") or "")
        self.cnpj_cpf.setText(dados.get("cnpj_cpf") or "")
        self.endereco.setText(dados.get("endereco") or "")
        self.telefone.setText(dados.get("telefone") or "")

        self.pix_chave.setText(dados.get("pix_chave") or "")
        self.pix_nome.setText(dados.get("pix_nome") or "")
        self.pix_cidade.setText(dados.get("pix_cidade") or "")

        indice = self.impressao_comprovante.findData(
            dados.get("impressao_comprovante") or "perguntar"
        )
        self.impressao_comprovante.setCurrentIndex(max(indice, 0))

        self.carregar_logo()
        self.carregar_usuarios()

    def carregar_logo(self):
        conteudo = buscar_logo_bytes()

        if conteudo:
            pixmap = QPixmap()
            pixmap.loadFromData(conteudo)
            self.logo_preview.setText("")
            self.logo_preview.setPixmap(
                pixmap.scaled(
                    110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )
        else:
            self.logo_preview.setPixmap(QPixmap())
            self.logo_preview.setText("Sem logo")

    def carregar_usuarios(self):
        self.usuarios = listar_usuarios()
        self.preencher_tabela_usuarios()

    def preencher_tabela_usuarios(self):
        self.tabela_usuarios.setRowCount(len(self.usuarios))

        for linha, usuario in enumerate(self.usuarios):
            self.tabela_usuarios.setItem(
                linha, 0, QTableWidgetItem(usuario["nome"])
            )
            self.tabela_usuarios.setItem(
                linha, 1, QTableWidgetItem(usuario["email"])
            )
            self.tabela_usuarios.setItem(
                linha, 2, QTableWidgetItem("Sim" if usuario["admin"] else "Não")
            )
            self.tabela_usuarios.setItem(
                linha,
                3,
                QTableWidgetItem("Ativo" if usuario["ativo"] else "Inativo"),
            )

            acoes = QWidget()
            acoes_layout = QHBoxLayout(acoes)
            acoes_layout.setContentsMargins(4, 2, 4, 2)

            bt_admin = QPushButton(
                "Remover Admin" if usuario["admin"] else "Tornar Admin"
            )
            bt_admin.clicked.connect(
                lambda _, u=usuario: self.alternar_admin(u)
            )

            bt_ativo = QPushButton(
                "Desativar" if usuario["ativo"] else "Ativar"
            )
            bt_ativo.clicked.connect(
                lambda _, u=usuario: self.alternar_ativo(u)
            )

            acoes_layout.addWidget(bt_admin)
            acoes_layout.addWidget(bt_ativo)

            self.tabela_usuarios.setCellWidget(linha, 4, acoes)

    # ==========================================
    # AÇÕES: LOJA / PIX
    # ==========================================

    def selecionar_logo(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Logo", "", "Imagens (*.png *.jpg *.jpeg)"
        )

        if not caminho:
            return

        response = enviar_logo(caminho)

        if response.status_code == 200:
            self.carregar_logo()
        else:
            self._exibir_erro(response)

    def salvar_loja(self):
        response = atualizar_configuracoes({
            "nome_loja": self.nome_loja.text(),
            "cnpj_cpf": self.cnpj_cpf.text(),
            "endereco": self.endereco.text(),
            "telefone": self.telefone.text(),
            "impressao_comprovante": self.impressao_comprovante.currentData(),
        })

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Dados da loja atualizados.")
        else:
            self._exibir_erro(response)

    def salvar_pix(self):
        response = atualizar_configuracoes({
            "pix_chave": self.pix_chave.text(),
            "pix_nome": self.pix_nome.text(),
            "pix_cidade": self.pix_cidade.text(),
        })

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Dados do PIX atualizados.")
        else:
            self._exibir_erro(response)

    # ==========================================
    # AÇÕES: USUÁRIOS
    # ==========================================

    def novo_usuario(self):
        tela = CadastroUsuarioWindow()

        if tela.exec() != QDialog.Accepted:
            return

        dados = tela.dados

        response = cadastrar_usuario(
            dados["nome"], dados["email"], dados["senha"]
        )

        if response.status_code != 200:
            self._exibir_erro(response)
            return

        if dados["admin"]:
            novo_id = response.json()["data"]["id"]
            definir_admin(novo_id, True)

        QMessageBox.information(self, "Sucesso", "Usuário cadastrado.")
        self.carregar_usuarios()

    def alternar_admin(self, usuario):
        response = definir_admin(usuario["id"], not usuario["admin"])

        if response.status_code == 200:
            self.carregar_usuarios()
        else:
            self._exibir_erro(response)

    def alternar_ativo(self, usuario):
        response = definir_ativo(usuario["id"], not usuario["ativo"])

        if response.status_code == 200:
            self.carregar_usuarios()
        else:
            self._exibir_erro(response)

    # ==========================================
    # HELPER DE ERRO
    # ==========================================

    def _exibir_erro(self, response):
        try:
            erro = response.json()["detail"]
        except Exception:
            erro = response.text

        QMessageBox.critical(self, "Erro", erro)
