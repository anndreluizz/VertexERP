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
    QInputDialog,
)

from services.categoria_despesa_service import (
    listar_categorias_despesa,
    cadastrar_categoria_despesa,
    atualizar_categoria_despesa,
    excluir_categoria_despesa,
)


class GerenciarCategoriasDespesaDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.categorias = []

        self.setWindowTitle("Gerenciar Categorias de Despesa")
        self.resize(480, 480)
        self.setStyleSheet("background:white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Categorias de Despesa")
        titulo.setStyleSheet(
            "background:transparent; font-size:18px; "
            "font-weight:bold; color:#202225;"
        )
        layout.addWidget(titulo)

        nova_layout = QHBoxLayout()

        self.novo_nome = QLineEdit()
        self.novo_nome.setPlaceholderText("Nova categoria...")
        self.novo_nome.setMinimumHeight(40)
        self.novo_nome.setStyleSheet("""
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
        self.novo_nome.returnPressed.connect(self.adicionar)

        bt_adicionar = QPushButton("+ Adicionar")
        bt_adicionar.setAutoDefault(False)
        bt_adicionar.setMinimumHeight(40)
        bt_adicionar.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                color:white;
                font-weight:bold;
                border-radius:8px;
                padding:0 16px;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
        """)
        bt_adicionar.clicked.connect(self.adicionar)

        nova_layout.addWidget(self.novo_nome)
        nova_layout.addWidget(bt_adicionar)

        layout.addLayout(nova_layout)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(1)
        self.tabela.setHorizontalHeaderLabels(["Nome"])
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

        bt_editar = QPushButton("Editar")
        bt_editar.setAutoDefault(False)
        bt_editar.setStyleSheet("""
            QPushButton {
                background:#1565C0;
                color:white;
                font-weight:bold;
                border-radius:8px;
                padding:8px 16px;
            }
            QPushButton:hover {
                background:#0D47A1;
            }
        """)
        bt_editar.clicked.connect(self.editar)

        bt_excluir = QPushButton("Excluir")
        bt_excluir.setAutoDefault(False)
        bt_excluir.setStyleSheet("""
            QPushButton {
                background:#C62828;
                color:white;
                font-weight:bold;
                border-radius:8px;
                padding:8px 16px;
            }
            QPushButton:hover {
                background:#B71C1C;
            }
        """)
        bt_excluir.clicked.connect(self.excluir)

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

        rodape.addWidget(bt_editar)
        rodape.addWidget(bt_excluir)
        rodape.addStretch()
        rodape.addWidget(bt_fechar)

        layout.addLayout(rodape)

        self.carregar()

    # ======================================

    def carregar(self):

        self.categorias = listar_categorias_despesa()

        self.tabela.setRowCount(len(self.categorias))

        for linha, categoria in enumerate(self.categorias):
            self.tabela.setItem(
                linha, 0, QTableWidgetItem(categoria.get("nome", ""))
            )

    def _categoria_selecionada(self):

        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(
                self, "Aviso", "Selecione uma categoria."
            )
            return None

        return self.categorias[linha]

    def adicionar(self):

        nome = self.novo_nome.text().strip()

        if not nome:
            return

        response = cadastrar_categoria_despesa(nome)

        if response.status_code == 200:
            self.novo_nome.clear()
            self.carregar()
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def editar(self):

        categoria = self._categoria_selecionada()

        if categoria is None:
            return

        novo_nome, ok = QInputDialog.getText(
            self,
            "Editar categoria",
            "Nome da categoria:",
            QLineEdit.Normal,
            categoria.get("nome", ""),
        )

        if not ok:
            return

        novo_nome = novo_nome.strip()

        if not novo_nome:
            return

        response = atualizar_categoria_despesa(
            categoria["id"], novo_nome
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

    def excluir(self):

        categoria = self._categoria_selecionada()

        if categoria is None:
            return

        resposta = QMessageBox.question(
            self,
            "Excluir categoria",
            f"Excluir a categoria \"{categoria.get('nome')}\"?",
        )

        if resposta != QMessageBox.Yes:
            return

        response = excluir_categoria_despesa(categoria["id"])

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
