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
)

from services.fornecedor_service import (
    listar_fornecedores,
)


class PesquisaFornecedorWindow(QDialog):

    def __init__(self):
        super().__init__()

        self.fornecedor = None

        self.fornecedores = []

        self.setWindowTitle(
            "Pesquisar Fornecedor"
        )

        self.resize(900, 550)

        layout = QVBoxLayout(self)

        titulo = QLabel(
            "PESQUISA DE FORNECEDORES"
        )

        titulo.setAlignment(Qt.AlignCenter)

        titulo.setStyleSheet("""
            font-size:22px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        barra = QHBoxLayout()

        self.pesquisa = QLineEdit()

        self.pesquisa.setPlaceholderText(
            "Pesquisar..."
        )

        barra.addWidget(self.pesquisa)

        layout.addLayout(barra)

        self.tabela = QTableWidget()

        self.tabela.setColumnCount(5)

        self.tabela.setHorizontalHeaderLabels([
            "Razão Social",
            "Nome Fantasia",
            "CNPJ",
            "Cidade",
            "Estado",
        ])

        self.tabela.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.tabela.setAlternatingRowColors(True)

        self.tabela.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self.tabela.setSelectionMode(
            QTableWidget.SingleSelection
        )

        self.tabela.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        self.tabela.verticalHeader().setVisible(False)

        layout.addWidget(self.tabela)

        botoes = QHBoxLayout()

        self.bt_cancelar = QPushButton("Cancelar")

        self.bt_selecionar = QPushButton("Selecionar")

        self.bt_selecionar.setStyleSheet("""
            QPushButton{
                background:#1565C0;
                color:white;
                font-weight:bold;
            }
            QPushButton:hover{
                background:#0D47A1;
            }
        """)

        botoes.addStretch()

        botoes.addWidget(self.bt_cancelar)

        botoes.addWidget(self.bt_selecionar)

        layout.addLayout(botoes)

        self.bt_cancelar.clicked.connect(
            self.reject
        )

        self.bt_selecionar.clicked.connect(
            self.selecionar
        )

        self.tabela.doubleClicked.connect(
            lambda index: self.selecionar()
        )

        self.pesquisa.textChanged.connect(
            self.filtrar
        )

        self.carregar()

        self.pesquisa.setFocus()

    # ==========================================
    # CARREGAR
    # ==========================================

    def carregar(self):

        self.fornecedores = listar_fornecedores()

        self.preencher_tabela(self.fornecedores)

    # ==========================================
    # PREENCHER TABELA
    # ==========================================

    def preencher_tabela(self, fornecedores):

        self.tabela.setRowCount(len(fornecedores))

        for linha, fornecedor in enumerate(fornecedores):

            item_razao = QTableWidgetItem(
                fornecedor["razao_social"]
            )

            item_razao.setData(Qt.UserRole, fornecedor)

            self.tabela.setItem(linha, 0, item_razao)

            self.tabela.setItem(
                linha,
                1,
                QTableWidgetItem(
                    fornecedor.get("nome_fantasia", "") or ""
                )
            )

            self.tabela.setItem(
                linha,
                2,
                QTableWidgetItem(
                    fornecedor["cnpj"]
                )
            )

            self.tabela.setItem(
                linha,
                3,
                QTableWidgetItem(
                    fornecedor.get("cidade", "") or ""
                )
            )

            self.tabela.setItem(
                linha,
                4,
                QTableWidgetItem(
                    fornecedor.get("estado", "") or ""
                )
            )

    # ==========================================
    # FILTRAR
    # ==========================================

    def filtrar(self):

        texto = (
            self.pesquisa.text()
            .lower()
            .strip()
        )

        if texto == "":
            self.preencher_tabela(self.fornecedores)
            return

        lista = []

        for fornecedor in self.fornecedores:

            if (
                texto in fornecedor["razao_social"].lower()
                or texto in (
                    fornecedor.get("nome_fantasia", "") or ""
                ).lower()
                or texto in fornecedor["cnpj"].lower()
            ):
                lista.append(fornecedor)

        self.preencher_tabela(lista)

    # ==========================================
    # SELECIONAR
    # ==========================================

    def selecionar(self):

        linha = self.tabela.currentRow()

        if linha < 0:
            return

        item = self.tabela.item(linha, 0)

        self.fornecedor = item.data(Qt.UserRole)

        self.accept()