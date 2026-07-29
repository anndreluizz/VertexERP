from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from services.user_service import (
    listar_usuarios,
    atualizar_usuario,
    criar_usuario,
)


class NovoUsuarioDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("+ Novo Usuário")
        self.setFixedSize(400, 420)
        self.setStyleSheet("background:white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        titulo = QLabel("+ Novo Usuário")
        titulo.setStyleSheet(
            "background:transparent; font-size:18px; "
            "font-weight:bold; color:#202225;"
        )

        subtitulo = QLabel(
            "Crie o acesso de um novo funcionário ao sistema."
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(
            "background:transparent; font-size:12px; color:gray;"
        )

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(10)

        self.nome = self._campo(layout, "NOME COMPLETO", "Nome")
        self.email = self._campo(
            layout, "E-MAIL", "email@exemplo.com"
        )
        self.senha = self._campo(
            layout, "SENHA", "••••••", senha=True
        )
        self.confirmar = self._campo(
            layout, "CONFIRMAR SENHA", "••••••", senha=True
        )

        layout.addStretch()

        botoes = QHBoxLayout()

        bt_cancelar = QPushButton("Cancelar")
        bt_cancelar.setMinimumHeight(44)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.setStyleSheet("""
            QPushButton {
                background:#f4f5f7;
                color:#202225;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#e8e8e8;
            }
        """)
        bt_cancelar.clicked.connect(self.reject)

        bt_criar = QPushButton("Cadastrar")
        bt_criar.setMinimumHeight(44)
        bt_criar.setAutoDefault(False)
        bt_criar.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                color:white;
                font-weight:bold;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
        """)
        bt_criar.clicked.connect(self.criar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(bt_criar)

        layout.addLayout(botoes)

        self.nome.setFocus()

    def _campo(self, layout, rotulo, placeholder, senha=False):

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(
            "background:transparent; font-size:10px; "
            "font-weight:bold; color:gray;"
        )

        campo = QLineEdit()
        campo.setPlaceholderText(placeholder)
        campo.setMinimumHeight(40)
        campo.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 13px;
                color: #202225;
            }
            QLineEdit:focus {
                border: 1px solid #2E7D32;
            }
        """)

        if senha:
            campo.setEchoMode(QLineEdit.Password)

        layout.addWidget(lbl)
        layout.addWidget(campo)

        return campo

    def criar(self):

        nome = self.nome.text().strip()
        email = self.email.text().strip()
        senha = self.senha.text()

        if not nome or not email or not senha:
            QMessageBox.warning(
                self, "Atenção", "Preencha todos os campos."
            )
            return

        if senha != self.confirmar.text():
            QMessageBox.warning(
                self, "Atenção", "As senhas não coincidem."
            )
            return

        response = criar_usuario(nome, email, senha)

        if response.status_code == 200:
            self.accept()
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))


class GerenciarUsuariosDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.usuarios = []

        self.setWindowTitle("Gerenciar Usuários")
        self.resize(640, 480)
        self.setStyleSheet("background:white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        cabecalho = QHBoxLayout()

        titulo = QLabel("Gerenciar Usuários")
        titulo.setStyleSheet(
            "background:transparent; font-size:18px; "
            "font-weight:bold; color:#202225;"
        )

        bt_novo = QPushButton("+ Novo Usuário")
        bt_novo.setAutoDefault(False)
        bt_novo.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                color:white;
                font-weight:bold;
                border-radius:8px;
                padding:8px 16px;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
        """)
        bt_novo.clicked.connect(self.novo_usuario)

        cabecalho.addWidget(titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(bt_novo)

        layout.addLayout(cabecalho)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(4)
        self.tabela.setHorizontalHeaderLabels(
            ["Nome", "E-mail", "Status", "Admin"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela.verticalHeader().setDefaultSectionSize(40)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SingleSelection)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                color: #202225;
                background: white;
                alternate-background-color: #f8f9fb;
            }
            QTableWidget::item:selected {
                background: #1565C0;
                color: white;
            }
            QHeaderView::section {
                background: #f4f5f7;
                color: #202225;
                font-weight: bold;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #e0e0e0;
            }
        """)

        layout.addWidget(self.tabela, stretch=1)

        rodape = QHBoxLayout()

        self.bt_ativar_desativar = QPushButton("Ativar / Desativar")
        self.bt_ativar_desativar.setAutoDefault(False)
        self.bt_ativar_desativar.setStyleSheet("""
            QPushButton {
                background:#C62828;
                color:white;
                font-weight:bold;
                border-radius:8px;
                padding:8px 14px;
            }
            QPushButton:hover {
                background:#B71C1C;
            }
        """)
        self.bt_ativar_desativar.clicked.connect(
            self.alternar_ativo
        )

        self.bt_admin = QPushButton("Tornar / Remover Admin")
        self.bt_admin.setAutoDefault(False)
        self.bt_admin.setStyleSheet("""
            QPushButton {
                background:#1565C0;
                color:white;
                font-weight:bold;
                border-radius:8px;
                padding:8px 14px;
            }
            QPushButton:hover {
                background:#0D47A1;
            }
        """)
        self.bt_admin.clicked.connect(self.alternar_admin)

        bt_fechar = QPushButton("Fechar")
        bt_fechar.setAutoDefault(False)
        bt_fechar.setStyleSheet("""
            QPushButton {
                background:#f4f5f7;
                color:#202225;
                border-radius:8px;
                padding:8px 20px;
            }
            QPushButton:hover {
                background:#e8e8e8;
            }
        """)
        bt_fechar.clicked.connect(self.accept)

        rodape.addWidget(self.bt_ativar_desativar)
        rodape.addWidget(self.bt_admin)
        rodape.addStretch()
        rodape.addWidget(bt_fechar)

        layout.addLayout(rodape)

        self.carregar()

    # ======================================

    def carregar(self):

        self.usuarios = listar_usuarios()

        self.tabela.setRowCount(len(self.usuarios))

        for linha, usuario in enumerate(self.usuarios):

            self.tabela.setItem(
                linha, 0, QTableWidgetItem(usuario.get("nome") or "")
            )
            self.tabela.setItem(
                linha, 1, QTableWidgetItem(usuario.get("email") or "")
            )
            self.tabela.setItem(
                linha,
                2,
                QTableWidgetItem(
                    "Ativo" if usuario.get("ativo", True) else "Inativo"
                ),
            )
            self.tabela.setItem(
                linha,
                3,
                QTableWidgetItem(
                    "Sim" if usuario.get("admin") else "Não"
                ),
            )

    def _usuario_selecionado(self):

        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(
                self, "Aviso", "Selecione um usuário."
            )
            return None

        return self.usuarios[linha]

    def novo_usuario(self):

        dialogo = NovoUsuarioDialog(parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        self.carregar()

    def alternar_ativo(self):

        usuario = self._usuario_selecionado()

        if usuario is None:
            return

        novo_status = not usuario.get("ativo", True)

        resposta = QMessageBox.question(
            self,
            "Confirmar",
            (
                f"Desativar o acesso de {usuario['nome']}?"
                if not novo_status
                else f"Reativar o acesso de {usuario['nome']}?"
            ),
        )

        if resposta != QMessageBox.Yes:
            return

        response = atualizar_usuario(
            usuario["id"], {"ativo": novo_status}
        )

        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def alternar_admin(self):

        usuario = self._usuario_selecionado()

        if usuario is None:
            return

        novo_admin = not usuario.get("admin", False)

        resposta = QMessageBox.question(
            self,
            "Confirmar",
            (
                f"Tornar {usuario['nome']} administrador?"
                if novo_admin
                else f"Remover {usuario['nome']} da administração?"
            ),
        )

        if resposta != QMessageBox.Yes:
            return

        response = atualizar_usuario(
            usuario["id"], {"admin": novo_admin}
        )

        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))
