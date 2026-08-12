from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QDialog,
    QAbstractItemView,
)

from telas.pagamento_compra import PagamentoCompraWindow

from telas.pesquisa_fornecedor import (
    PesquisaFornecedorWindow,
)

from widgets.dialogs.pesquisa_window import PesquisaWindow

from services.pdv_service import (
    buscar_produto,
)

from services.compra_service import (
    cadastrar_compra,
)

from services.produto_service import listar_produtos


class Compras(QWidget):

    def __init__(self):
        super().__init__()

        self.itens = []

        layout = QVBoxLayout(self)

        titulo = QLabel("COMPRAS")

        titulo.setAlignment(Qt.AlignCenter)

        titulo.setStyleSheet("""
            font-size:24px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        # ==========================================
        # FORNECEDOR
        # ==========================================

        dados_layout = QHBoxLayout()

        dados_layout.addWidget(QLabel("Fornecedor"))

        self.fornecedor_id = None

        self.fornecedor = QLineEdit()

        self.fornecedor.setReadOnly(True)

        self.fornecedor.setPlaceholderText(
            "Selecione um fornecedor..."
        )

        self.bt_fornecedor = QPushButton(
            "Pesquisar"
        )

        self.fornecedor.setMinimumWidth(400)

        dados_layout.addWidget(self.fornecedor)

        dados_layout.addWidget(self.bt_fornecedor)

        layout.addLayout(dados_layout)

        # ==========================================
        # OBSERVAÇÃO
        # ==========================================

        self.observacao = QLineEdit()

        self.observacao.setPlaceholderText(
            "Observação (opcional)"
        )

        layout.addWidget(self.observacao)

        # ==========================================
        # ADICIONAR PRODUTO
        # ==========================================

        produto_layout = QHBoxLayout()

        self.codigo = QLineEdit()

        self.codigo.setPlaceholderText(
            "Código, código de barras ou F3 para pesquisar"
        )

        self.bt_pesquisar = QPushButton("Pesquisar")

        self.bt_adicionar = QPushButton("Adicionar")

        produto_layout.addWidget(self.codigo)

        produto_layout.addWidget(self.bt_pesquisar)

        produto_layout.addWidget(self.bt_adicionar)

        layout.addLayout(produto_layout)

        # ==========================================
        # TABELA DE ITENS
        # ==========================================

        self.tabela = QTableWidget()

        self.tabela.setColumnCount(5)

        self.tabela.setHorizontalHeaderLabels([
            "Código",
            "Produto",
            "Qtde",
            "Custo",
            "Subtotal",
        ])

        self.tabela.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.tabela.setAlternatingRowColors(True)

        self.tabela.verticalHeader().setVisible(False)

        # Permite editar apenas com duplo clique
        self.tabela.setEditTriggers(
            QAbstractItemView.DoubleClicked
        )

        # Evento disparado quando uma célula é alterada
        self.tabela.itemChanged.connect(
            self.item_alterado
        )

        layout.addWidget(self.tabela)

        # ==========================================
        # RODAPÉ
        # ==========================================

        rodape = QHBoxLayout()

        self.total = QLabel("TOTAL: R$ 0,00")

        self.total.setStyleSheet("""
            font-size:24px;
            font-weight:bold;
            color:#1565C0;
        """)

        self.bt_cancelar = QPushButton("Cancelar Compra")

        self.bt_cancelar.setStyleSheet("""
            QPushButton{
                background:#C62828;
                color:white;
                font-size:15px;
                font-weight:bold;
            }
            QPushButton:hover{
                background:#B71C1C;
            }
        """)

        self.bt_finalizar = QPushButton("Finalizar Compra")

        self.bt_finalizar.setStyleSheet("""
            QPushButton{
                background:#2E7D32;
                color:white;
                font-size:15px;
                font-weight:bold;
            }
            QPushButton:hover{
                background:#1B5E20;
            }
        """)

        rodape.addWidget(self.bt_cancelar)

        rodape.addStretch()

        rodape.addWidget(self.total)

        rodape.addStretch()

        rodape.addWidget(self.bt_finalizar)

        layout.addLayout(rodape)

        # ==========================================
        # EVENTOS
        # ==========================================

        self.bt_adicionar.clicked.connect(
            self.adicionar_produto
        )

        self.bt_pesquisar.clicked.connect(
            self.pesquisar_produto
        )

        self.codigo.returnPressed.connect(
            self.adicionar_produto
        )

        self.bt_cancelar.clicked.connect(
            self.cancelar_compra
        )

        self.bt_finalizar.clicked.connect(
            self.finalizar_compra
        )

        self.bt_fornecedor.clicked.connect(
            self.buscar_fornecedor
        )

        # Atalho DELETE remove o item selecionado
        QShortcut(
            QKeySequence("Delete"),
            self,
            self.remover_item,
        )

        # Atalho F3 abre a pesquisa de produtos
        QShortcut(
            QKeySequence("F3"),
            self,
            self.pesquisar_produto,
        )

    # ==========================================
    # BUSCAR FORNECEDOR
    # ==========================================

    def buscar_fornecedor(self):

        tela = PesquisaFornecedorWindow()

        if tela.exec() != QDialog.Accepted:
            return

        self.fornecedor_id = tela.fornecedor["id"]

        self.fornecedor.setText(
            tela.fornecedor["razao_social"]
        )

    # ==========================================
    # PESQUISAR PRODUTO
    # ==========================================

    def pesquisar_produto(self):

        produtos = listar_produtos()

        tela = PesquisaWindow(

            titulo="Pesquisar Produto",

            colunas=[
                "Código",
                "Nome",
                "Categoria",
                "Estoque",
                "Preço",
            ],

            campos=[
                "codigo",
                "nome",
                "categoria",
                "estoque",
                "preco_venda",
            ],

            dados=produtos,

            chave_pesquisa="nome",
        )

        if tela.exec() != QDialog.Accepted:
            return

        self.codigo.setText(
            str(tela.selecionado["codigo"])
        )

        self.adicionar_produto()

    # ==========================================
    # ADICIONAR PRODUTO
    # ==========================================

    def adicionar_produto(self):

        codigo = self.codigo.text().strip()

        if codigo == "":
            return

        produto = buscar_produto(codigo)

        if produto is None:

            QMessageBox.warning(
                self,
                "Erro",
                "Produto não encontrado."
            )

            self.codigo.clear()

            self.codigo.setFocus()

            return

        encontrou = False

        linha_encontrada = -1

        for indice, item in enumerate(self.itens):

            if item["id"] == produto["id"]:

                item["quantidade"] += 1

                encontrou = True

                linha_encontrada = indice

                break

        if not encontrou:

            self.itens.append(
                {
                    "id": produto["id"],
                    "codigo": produto["codigo"],
                    "nome": produto["nome"],
                    "preco": float(
                        produto.get("preco_custo") or 0
                    ),
                    "quantidade": 1,
                }
            )

        self.atualizar_tabela()

        if encontrou:

            self.tabela.selectRow(
                linha_encontrada
            )

            self.tabela.scrollToItem(
                self.tabela.item(
                    linha_encontrada,
                    0
                )
            )

        else:

            self.tabela.selectRow(
                len(self.itens) - 1
            )

        self.codigo.clear()

        self.codigo.setFocus()

    # ==========================================
    # ATUALIZAR TABELA
    # ==========================================

    def atualizar_tabela(self):
        self.tabela.blockSignals(True)
        self.tabela.setRowCount(len(self.itens))

        total = 0

        for linha, item in enumerate(self.itens):

            subtotal = (
                item["preco"]
                * item["quantidade"]
            )

            total += subtotal

            codigo = QTableWidgetItem(
                str(item["codigo"])
            )

            codigo.setFlags(
                codigo.flags() & ~Qt.ItemIsEditable
            )

            self.tabela.setItem(
                linha,
                0,
                codigo
            )

            produto = QTableWidgetItem(
                item["nome"]
            )

            produto.setFlags(
                produto.flags() & ~Qt.ItemIsEditable
            )

            self.tabela.setItem(
                linha,
                1,
                produto
            )

            self.tabela.setItem(
                linha,
                2,
                QTableWidgetItem(
                    str(item["quantidade"])
                )
            )

            self.tabela.setItem(
                linha,
                3,
                QTableWidgetItem(
                    f"R$ {item['preco']:.2f}"
                )
            )

            subtotal_item = QTableWidgetItem(
                f"R$ {subtotal:.2f}"
            )

            subtotal_item.setFlags(
                subtotal_item.flags() & ~Qt.ItemIsEditable
            )

            self.tabela.setItem(
                linha,
                4,
                subtotal_item
            )

        self.total.setText(
            f"TOTAL: R$ {total:.2f}"

        )
        self.tabela.blockSignals(False)

    # ==========================================
    # ITEM ALTERADO
    # ==========================================

    def item_alterado(self, item):

        linha = item.row()
        coluna = item.column()

        if linha >= len(self.itens):
            return

        try:

            # Alteração da quantidade
            if coluna == 2:

                quantidade = int(item.text())

                if quantidade <= 0:
                    quantidade = 1

                self.itens[linha]["quantidade"] = quantidade

            # Alteração do custo
            elif coluna == 3:

                texto = (
                    item.text()
                    .replace("R$", "")
                    .replace(",", ".")
                    .strip()
                )

                preco = float(texto)

                if preco < 0:
                    preco = 0

                self.itens[linha]["preco"] = preco

            else:
                return

            # Atualiza a tabela e recalcula os valores
            self.atualizar_tabela()

        except Exception:

            QMessageBox.warning(
                self,
                "Valor inválido",
                "Digite um valor válido."
            )

            self.atualizar_tabela()

    # ==========================================
    # REMOVER ITEM
    # ==========================================

    def remover_item(self):

        linha = self.tabela.currentRow()

        if linha < 0:

            QMessageBox.warning(
                self,
                "Aviso",
                "Selecione um item."
            )

            return

        item = self.itens[linha]

        resposta = QMessageBox.question(
            self,
            "Remover Item",
            f"Deseja remover o produto\n\n{item['nome']} ?"
        )

        if resposta != QMessageBox.Yes:
            return

        del self.itens[linha]

        self.atualizar_tabela()

    # ==========================================
    # CANCELAR COMPRA
    # ==========================================

    def cancelar_compra(self):

        if not self.itens:
            return

        resposta = QMessageBox.question(
            self,
            "Cancelar Compra",
            "Deseja cancelar esta compra?"
        )

        if resposta != QMessageBox.Yes:
            return

        self._limpar()

    # ==========================================
    # FINALIZAR COMPRA
    # ==========================================

    def finalizar_compra(self):

        if self.fornecedor_id is None:

            QMessageBox.warning(
                self,
                "Fornecedor",
                "Selecione um fornecedor."
            )

            return

        if not self.itens:

            QMessageBox.warning(
                self,
                "Aviso",
                "Nenhum produto foi adicionado."
            )

            return

        tela = PagamentoCompraWindow()

        if tela.exec() != QDialog.Accepted:
            return

        itens = []

        for item in self.itens:

            itens.append({
                "produto_id": item["id"],
                "quantidade": item["quantidade"],
                "valor_unitario": item["preco"],
            })

        dados = {

            "fornecedor_id": self.fornecedor_id,

            "observacao": self.observacao.text() or None,

            "forma_pagamento": tela.forma_pagamento,

            "data_vencimento": tela.data_vencimento,

            "itens": itens,
        }

        response = cadastrar_compra(dados)

        if response.status_code in (200, 201):

            QMessageBox.information(
                self,
                "Sucesso",
                "Compra realizada com sucesso!"
            )

            self._limpar()

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
    # LIMPAR TELA
    # ==========================================

    def _limpar(self):

        self.itens.clear()

        self.tabela.setRowCount(0)

        self.fornecedor_id = None

        self.fornecedor.clear()

        self.total.setText("TOTAL: R$ 0,00")

        self.observacao.clear()

        self.codigo.clear()

        self.codigo.setFocus()