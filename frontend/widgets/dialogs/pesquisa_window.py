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


class PesquisaWindow(QDialog):

    def __init__(self, titulo, colunas, campos, dados, chave_pesquisa):
        super().__init__()

        self.setWindowTitle(titulo)
        self.resize(900, 550)

        self.dados = dados
        self.campos = campos
        self.chave_pesquisa = chave_pesquisa
        self.selecionado = None

        layout = QVBoxLayout(self)

        titulo_lbl = QLabel(titulo)
        titulo_lbl.setAlignment(Qt.AlignCenter)
        titulo_lbl.setStyleSheet("font-size:22px; font-weight:bold;")
        layout.addWidget(titulo_lbl)

        self.pesquisa = QLineEdit()
        self.pesquisa.setPlaceholderText("Pesquisar...")
        layout.addWidget(self.pesquisa)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(len(colunas))
        self.tabela.setHorizontalHeaderLabels(colunas)
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.tabela)

        botoes = QHBoxLayout()
        cancelar = QPushButton("Cancelar")
        selecionar = QPushButton("Selecionar")
        botoes.addStretch()
        botoes.addWidget(cancelar)
        botoes.addWidget(selecionar)
        layout.addLayout(botoes)

        cancelar.clicked.connect(self.reject)
        selecionar.clicked.connect(self.selecionar)
        self.tabela.doubleClicked.connect(self.selecionar)
        self.pesquisa.textChanged.connect(self.filtrar)

        self.preencher_tabela(self.dados)

    # ==========================================
    # PREENCHER TABELA
    # ==========================================
    def preencher_tabela(self, dados):
        self.tabela.setRowCount(len(dados))

        for linha, registro in enumerate(dados):
            for coluna, campo in enumerate(self.campos):
                valor = registro.get(campo, "")
                if valor is None:
                    valor = ""

                item = QTableWidgetItem(str(valor))
                # guarda o registro completo no primeiro item da linha,
                # evitando ter que procurar de novo em self.dados na hora de selecionar
                if coluna == 0:
                    item.setData(Qt.UserRole, registro)

                self.tabela.setItem(linha, coluna, item)

    # ==========================================
    # FILTRAR
    # ==========================================
    def filtrar(self):
        texto = self.pesquisa.text().lower().strip()

        if texto == "":
            self.preencher_tabela(self.dados)
            return

        lista = [
            registro
            for registro in self.dados
            if texto in str(registro.get(self.chave_pesquisa, "")).lower()
        ]

        self.preencher_tabela(lista)

    # ==========================================
    # SELECIONAR
    # ==========================================
    def selecionar(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            return

        item = self.tabela.item(linha, 0)
        if item is None:
            return

        self.selecionado = item.data(Qt.UserRole)
        self.accept()