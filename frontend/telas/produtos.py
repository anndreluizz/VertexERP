from PySide6.QtWidgets import QMessageBox

from telas.cadastro_produto import CadastroProdutoWindow

from services.produto_service import (
    listar_produtos,
    cadastrar_produto,
    atualizar_produto,
    excluir_produto,
)
from PySide6.QtCore import Qt

from PySide6.QtGui import QShortcut, QKeySequence

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
)


class Produtos(QWidget):

    def __init__(self):
        super().__init__()

        self.produtos = []

        layout = QVBoxLayout(self)

        titulo = QLabel("PRODUTOS")

        titulo.setAlignment(Qt.AlignCenter)

        titulo.setStyleSheet("""
            font-size:24px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        barra = QHBoxLayout()

        self.pesquisa = QLineEdit()

        self.pesquisa.setPlaceholderText(
            "Pesquisar produto..."
        )

        self.bt_pesquisar = QPushButton("Pesquisar")

        self.pesquisa.textChanged.connect(
            self.filtrar_produtos
        )

        self.bt_pesquisar.clicked.connect(
            self.filtrar_produtos
        )

        self.bt_novo = QPushButton("Novo Produto")

        self.bt_novo.setStyleSheet("""
            QPushButton{
                background:#2E7D32;
                color:white;
                font-weight:bold;
            }
            QPushButton:hover{
                background:#1B5E20;
            }
        """)

        barra.addWidget(self.pesquisa)

        barra.addWidget(self.bt_pesquisar)

        barra.addWidget(self.bt_novo)

        layout.addLayout(barra)

        self.tabela = QTableWidget()

        self.tabela.setColumnCount(7)

        self.tabela.setHorizontalHeaderLabels([
            "Código",
            "Barras",
            "Produto",
            "Categoria",
            "Estoque",
            "Venda",
            "Status",
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

        self.tabela.setShowGrid(False)

        self.tabela.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.tabela)

        rodape = QHBoxLayout()

        self.bt_editar = QPushButton("Editar")

        self.bt_editar.setStyleSheet("""
            QPushButton{
                background:#1565C0;
                color:white;
                font-weight:bold;
            }
            QPushButton:hover{
                background:#0D47A1;
            }
        """)

        self.bt_excluir = QPushButton("Excluir")

        self.bt_excluir.setStyleSheet("""
            QPushButton{
                background:#C62828;
                color:white;
                font-weight:bold;
            }
            QPushButton:hover{
                background:#B71C1C;
            }
        """)

        self.bt_atualizar = QPushButton("Atualizar")

        self.bt_atualizar.setStyleSheet("""
            QPushButton{
                background:#616161;
                color:white;
                font-weight:bold;
            }
            QPushButton:hover{
                background:#424242;
            }
        """)

        rodape.addWidget(self.bt_editar)

        rodape.addWidget(self.bt_excluir)

        rodape.addStretch()

        rodape.addWidget(self.bt_atualizar)

        layout.addLayout(rodape)

        # ==========================================
        # DICAS DE ATALHOS
        # ==========================================

        dicas = QLabel(
            "⌨️  Ctrl+N Novo produto    "
            "F5 Atualizar    "
            "Delete Excluir selecionado    "
            "🖱️ Duplo clique Editar"
        )

        dicas.setAlignment(Qt.AlignCenter)

        dicas.setStyleSheet("""
            color:#9E9E9E;
            font-size:12px;
            padding:6px;
        """)

        layout.addWidget(dicas)

        # ==========================================
        # EVENTOS
        # ==========================================

        self.bt_atualizar.clicked.connect(
            self.carregar
        )

        self.bt_novo.clicked.connect(
            self.novo_produto
        )

        self.bt_editar.clicked.connect(
            self.editar_produto
        )

        self.bt_excluir.clicked.connect(
            self.excluir_produto
        )

        self.pesquisa.returnPressed.connect(
            self.filtrar_produtos
        )

        self.tabela.doubleClicked.connect(
            lambda index: self.editar_produto()
        )

        # ==========================================
        # ATALHOS DE TECLADO
        # ==========================================

        QShortcut(
            QKeySequence("Delete"),
            self,
            self.excluir_produto
        )

        QShortcut(
            QKeySequence("F5"),
            self,
            self.carregar
        )

        QShortcut(
            QKeySequence("Ctrl+N"),
            self,
            self.novo_produto
        )

        self.carregar()

    # ==========================================
    # CARREGAR PRODUTOS
    # ==========================================

    def carregar(self):

        self.produtos = listar_produtos()

        self.preencher_tabela(self.produtos)

    # ==========================================
    # FILTRAR PRODUTOS
    # ==========================================

    def filtrar_produtos(self):

        texto = self.pesquisa.text().lower().strip()

        if texto == "":

            produtos = self.produtos

        else:

            produtos = []

            for produto in self.produtos:

                codigo = str(
                    produto["codigo"]
                ).lower()

                barras = str(
                    produto.get("codigo_barras") or ""
                ).lower()

                nome = str(
                    produto["nome"]
                ).lower()

                categoria = str(
                    produto.get("categoria") or ""
                ).lower()

                if (
                    texto in codigo
                    or texto in barras
                    or texto in nome
                    or texto in categoria
                ):

                    produtos.append(produto)

        self.preencher_tabela(produtos)

    # ==========================================
    # PREENCHER TABELA
    # ==========================================

    def preencher_tabela(self, produtos):

        self.tabela.setRowCount(len(produtos))

        for linha, produto in enumerate(produtos):

            self.tabela.setItem(
                linha,
                0,
                QTableWidgetItem(
                    str(produto["codigo"])
                )
            )

            self.tabela.setItem(
                linha,
                1,
                QTableWidgetItem(
                    produto.get(
                        "codigo_barras",
                        ""
                    ) or ""
                )
            )

            self.tabela.setItem(
                linha,
                2,
                QTableWidgetItem(
                    produto["nome"]
                )
            )

            self.tabela.setItem(
                linha,
                3,
                QTableWidgetItem(
                    produto.get(
                        "categoria",
                        ""
                    ) or ""
                )
            )

            self.tabela.setItem(
                linha,
                4,
                QTableWidgetItem(
                    str(produto["estoque"])
                )
            )

            self.tabela.setItem(
                linha,
                5,
                QTableWidgetItem(
                    f'R$ {float(produto["preco_venda"]):.2f}'
                )
            )

            status = (
                "Ativo"
                if produto.get("ativo", True)
                else "Inativo"
            )

            self.tabela.setItem(
                linha,
                6,
                QTableWidgetItem(status)
            )

    # ==========================================
    # NOVO PRODUTO
    # ==========================================

    def novo_produto(self):

        tela = CadastroProdutoWindow()

        if tela.exec() != QDialog.Accepted:
            return

        response = cadastrar_produto(
            tela.dados
        )

        if response.status_code == 201:

            QMessageBox.information(
                self,
                "Sucesso",
                "Produto cadastrado com sucesso."
            )

            self.carregar()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(
                self,
                "Erro",
                erro,
            )

    # ==========================================
    # EDITAR PRODUTO
    # ==========================================

    def editar_produto(self):

        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(
                self,
                "Aviso",
                "Selecione um produto."
            )
            return

        produto = self.produtos[linha]

        tela = CadastroProdutoWindow(produto)

        if tela.exec() != QDialog.Accepted:
            return

        response = atualizar_produto(
            produto["id"],
            tela.dados,
        )

        if response.status_code == 200:

            QMessageBox.information(
                self,
                "Sucesso",
                "Produto atualizado com sucesso."
            )

            self.carregar()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(
                self,
                "Erro",
                erro,
            )

    # ==========================================
    # EXCLUIR PRODUTO
    # ==========================================

    def excluir_produto(self):

        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(
                self,
                "Aviso",
                "Selecione um produto."
            )
            return

        produto = self.produtos[linha]

        resposta = QMessageBox.question(
            self,
            "Excluir Produto",
            f"Deseja excluir o produto\n\n{produto['nome']} ?"
        )

        if resposta != QMessageBox.Yes:
            return

        response = excluir_produto(
            produto["id"]
        )

        if response.status_code == 200:

            QMessageBox.information(
                self,
                "Sucesso",
                "Produto excluído."
            )

            self.carregar()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(
                self,
                "Erro",
                erro,
            )