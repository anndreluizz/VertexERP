from telas.pagamento import PagamentoWindow
from services.venda_service import finalizar_venda as enviar_venda
from services.pdv_service import buscar_produto

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
)


class PDV(QWidget):

    def __init__(self):
        super().__init__()

        self.itens = []

        layout = QVBoxLayout(self)

        titulo = QLabel("PONTO DE VENDA")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            font-size:24px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        pesquisa = QHBoxLayout()

        self.codigo = QLineEdit()
        self.codigo.setPlaceholderText(
            "Código ou Código de Barras"
        )

        self.bt_buscar = QPushButton("Buscar")

        self.bt_buscar.clicked.connect(
            self.adicionar_produto
        )

        self.codigo.returnPressed.connect(
            self.adicionar_produto
        )

        pesquisa.addWidget(self.codigo)
        pesquisa.addWidget(self.bt_buscar)

        layout.addLayout(pesquisa)

        self.tabela = QTableWidget()

        self.tabela.setColumnCount(5)

        self.tabela.setHorizontalHeaderLabels([
            "Código",
            "Produto",
            "Qtde",
            "Unitário",
            "Total",
        ])

        self.tabela.horizontalHeader().setStretchLastSection(True)

        layout.addWidget(self.tabela)

        total_layout = QHBoxLayout()

        self.bt_cancelar = QPushButton("Cancelar Venda")
        self.bt_finalizar = QPushButton("Finalizar Venda")

        self.bt_cancelar.setMinimumHeight(45)
        self.bt_finalizar.setMinimumHeight(45)

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

        self.total = QLabel("TOTAL: R$ 0,00")

        self.total.setStyleSheet("""
            font-size:26px;
            font-weight:bold;
            color:#1565C0;
        """)

        total_layout.addWidget(self.bt_cancelar)
        total_layout.addStretch()
        total_layout.addWidget(self.total)
        total_layout.addStretch()
        total_layout.addWidget(self.bt_finalizar)

        layout.addLayout(total_layout)

        self.bt_cancelar.clicked.connect(
            self.cancelar_venda
        )

        self.bt_finalizar.clicked.connect(
            self.finalizar_venda
        )

        self.codigo.setFocus()

    # ==================================================
    # ADICIONAR PRODUTO
    # ==================================================

    def adicionar_produto(self):

        codigo = self.codigo.text().strip()

        if not codigo:
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

        for item in self.itens:

            if item["id"] == produto["id"]:

                item["quantidade"] += 1

                encontrou = True

                break

        if not encontrou:

            self.itens.append(
                {
                    "id": produto["id"],
                    "codigo": produto["codigo"],
                    "nome": produto["nome"],
                    "preco": float(produto["preco"]),
                    "quantidade": 1,
                }
            )

        self.atualizar_tabela()

        self.codigo.clear()

        self.codigo.setFocus()

    # ==================================================
    # ATUALIZAR TABELA
    # ==================================================

    def atualizar_tabela(self):

        self.tabela.setRowCount(len(self.itens))

        total = 0

        for linha, item in enumerate(self.itens):
            subtotal = (
                    item["preco"] *
                    item["quantidade"]
            )

            total += subtotal

            self.tabela.setItem(
                linha,
                0,
                QTableWidgetItem(item["codigo"])
            )

            self.tabela.setItem(
                linha,
                1,
                QTableWidgetItem(item["nome"])
            )

            self.tabela.setItem(
                linha,
                2,
                QTableWidgetItem(str(item["quantidade"]))
            )

            self.tabela.setItem(
                linha,
                3,
                QTableWidgetItem(
                    f"R$ {item['preco']:.2f}"
                )
            )

            self.tabela.setItem(
                linha,
                4,
                QTableWidgetItem(
                    f"R$ {subtotal:.2f}"
                )
            )

        self.total.setText(
            f"TOTAL: R$ {total:.2f}"
        )

    # ==================================================
    # CANCELAR VENDA
    # ==================================================

    def cancelar_venda(self):

        if not self.itens:
            return

        resposta = QMessageBox.question(
            self,
            "Cancelar Venda",
            "Deseja cancelar esta venda?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if resposta == QMessageBox.No:
            return

        self.itens.clear()

        self.tabela.setRowCount(0)

        self.total.setText(
            "TOTAL: R$ 0,00"
        )

        self.codigo.clear()

        self.codigo.setFocus()

    # ==================================================
    # FINALIZAR VENDA
    # ==================================================

    def finalizar_venda(self):

        if not self.itens:
            QMessageBox.warning(
                self,
                "Aviso",
                "Nenhum produto foi adicionado."
            )

            return

        total = sum(
            item["preco"] * item["quantidade"]
            for item in self.itens
        )

        tela = PagamentoWindow(total)

        if tela.exec() != QDialog.Accepted:
            return

        try:

            response = enviar_venda(
                itens=self.itens,
                forma_pagamento=tela.forma_pagamento,
                cliente_id=None,
                desconto=0,
                observacao=None,
                data_vencimento=None,
            )

            if response.status_code == 201:

                QMessageBox.information(
                    self,
                    "Sucesso",
                    "Venda realizada com sucesso!"
                )

                self.itens.clear()

                self.tabela.setRowCount(0)

                self.total.setText(
                    "TOTAL: R$ 0,00"
                )

                self.codigo.clear()

                self.codigo.setFocus()

            else:

                try:
                    erro = response.json()

                    if isinstance(erro, dict):
                        erro = erro.get(
                            "detail",
                            str(erro)
                        )

                except Exception:
                    erro = response.text

                QMessageBox.critical(
                    self,
                    "Erro",
                    f"Erro ao finalizar a venda.\n\n{erro}"
                )

        except Exception as e:

            QMessageBox.critical(
                self,
                "Erro",
                str(e)
            )