from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
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

from design import tokens
from design.widgets import BotaoPerigo, BotaoPrimario, BotaoSecundario, BotaoSucesso, CampoTexto


class GerenciarCategoriasDespesaDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.categorias = []

        self.setWindowTitle("Gerenciar Categorias de Despesa")
        self.resize(480, 480)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        titulo = QLabel("Categorias de Despesa")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        layout.addWidget(titulo)

        nova_layout = QHBoxLayout()

        self.novo_nome = CampoTexto(
            "Nova categoria...", cor_foco=tokens.SECUNDARIA
        )
        self.novo_nome.returnPressed.connect(self.adicionar)

        bt_adicionar = BotaoSucesso("Adicionar", icone_nome="plus")
        bt_adicionar.setAutoDefault(False)
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
        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                alternate-background-color: {tokens.FUNDO};
            }}
            QTableWidget::item:selected {{
                background: {tokens.PRIMARIA};
                color: {tokens.TEXTO_CLARO};
            }}
            QHeaderView::section {{
                background: {tokens.FUNDO};
                color: {tokens.TEXTO};
                font-weight: 700;
                padding: 8px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
        """)

        layout.addWidget(self.tabela, stretch=1)

        rodape = QHBoxLayout()

        bt_editar = BotaoPrimario("Editar", icone_nome="edit-2")
        bt_editar.setAutoDefault(False)
        bt_editar.clicked.connect(self.editar)

        bt_excluir = BotaoPerigo("Excluir", icone_nome="trash-2")
        bt_excluir.setAutoDefault(False)
        bt_excluir.clicked.connect(self.excluir)

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.setAutoDefault(False)
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
