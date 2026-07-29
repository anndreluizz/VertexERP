from telas.pagamento import PagamentoWindow
from telas.buscar_produto import BuscarProdutoDialog
from telas.venda_concluida import VendaConcluidaDialog
from telas.cadastro_rapido import CadastroRapidoDialog
from services.venda_service import finalizar_venda as enviar_venda
from services.pdv_service import buscar_produto
from services.api import configuracoes

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
)


class BotaoAtalho(QFrame):

    clicado = Signal()

    def __init__(self, icone, titulo, atalho, cor):

        super().__init__()

        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(64)

        self.setStyleSheet(f"""
            QFrame {{
                background: {cor};
                border-radius: 10px;
            }}

            QLabel {{
                border: none;
                background: transparent;
                color: white;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(14)

        lbl_icone = QLabel(icone)
        lbl_icone.setStyleSheet("font-size:22px;")

        col_texto = QVBoxLayout()
        col_texto.setSpacing(0)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(
            "font-size:14px; font-weight:bold;"
        )

        lbl_atalho = QLabel(atalho)
        lbl_atalho.setStyleSheet("font-size:11px; color:#dddddd;")

        col_texto.addWidget(lbl_titulo)
        col_texto.addWidget(lbl_atalho)

        layout.addWidget(lbl_icone)
        layout.addLayout(col_texto)
        layout.addStretch()

    def mousePressEvent(self, event):
        self.clicado.emit()
        super().mousePressEvent(event)


class PDV(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.itens = []

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background:white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 20)
        layout.setSpacing(14)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()

        self.bt_voltar = QPushButton("←")
        self.bt_voltar.setFixedSize(36, 36)
        self.bt_voltar.setStyleSheet("""
            QPushButton {
                background:#f0f0f0;
                border-radius:8px;
                font-size:16px;
            }
            QPushButton:hover {
                background:#e0e0e0;
            }
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("FRENTE DE CAIXA")
        titulo.setStyleSheet(
            "background:transparent; font-size:20px; "
            "font-weight:bold; color:#202225;"
        )

        config = configuracoes()
        nome_loja = config.get("nome_loja") or ""

        self.lbl_loja = QLabel(nome_loja)
        self.lbl_loja.setStyleSheet(
            "background:transparent; font-size:11px; "
            "color:#2E7D32; font-weight:bold;"
        )

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(self.lbl_loja)

        self.bt_cancelar = QPushButton("Cancelar Venda")
        self.bt_cancelar.setStyleSheet("""
            QPushButton {
                background:#C62828;
                color:white;
                border-radius:8px;
                padding:8px 14px;
                font-weight:bold;
            }
            QPushButton:hover {
                background:#B71C1C;
            }
        """)
        self.bt_cancelar.clicked.connect(self.cancelar_venda)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addSpacing(12)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(self.bt_cancelar)

        layout.addLayout(cabecalho)

        # ======================
        # TABELA DE ITENS
        # ======================

        self.tabela = QTableWidget()

        self.tabela.setColumnCount(6)

        self.tabela.setHorizontalHeaderLabels([
            "Código",
            "Produto",
            "Qtde",
            "Unitário",
            "Total",
            "",
        ])

        self.tabela.horizontalHeader().setStretchLastSection(False)
        self.tabela.setColumnWidth(2, 120)
        self.tabela.setColumnWidth(5, 48)
        self.tabela.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.tabela.setStyleSheet("""
            QTableWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                gridline-color: #eeeeee;
                color: #202225;
                background: white;
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

        # ======================
        # RESUMO (ITENS / TOTAL)
        # ======================

        resumo = QHBoxLayout()

        col_itens = QVBoxLayout()
        col_itens.setSpacing(0)

        lbl_itens_titulo = QLabel("ITENS")
        lbl_itens_titulo.setStyleSheet(
            "font-size:12px; color:gray;"
        )

        self.lbl_itens_valor = QLabel("0")
        self.lbl_itens_valor.setStyleSheet(
            "font-size:26px; font-weight:bold;"
        )

        col_itens.addWidget(lbl_itens_titulo)
        col_itens.addWidget(self.lbl_itens_valor)

        self.total = QLabel("R$ 0,00")
        self.total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.total.setStyleSheet("""
            font-size:36px;
            font-weight:bold;
            color:#2E7D32;
        """)

        resumo.addLayout(col_itens)
        resumo.addStretch()
        resumo.addWidget(self.total)

        layout.addLayout(resumo)

        # ======================
        # BARRA DE ATALHOS
        # ======================

        barra = QHBoxLayout()
        barra.setSpacing(14)

        self.bt_buscar = BotaoAtalho(
            "🔍", "BUSCAR", "F1", "#2b2b2b"
        )
        self.bt_pagar = BotaoAtalho(
            "💳", "PAGAR", "F3", "#2E7D32"
        )
        self.bt_adicionar = BotaoAtalho(
            "➕", "ADICIONAR", "F4", "#1565C0"
        )

        self.bt_buscar.clicado.connect(self.abrir_busca)
        self.bt_pagar.clicado.connect(self.finalizar_venda)
        self.bt_adicionar.clicado.connect(self.abrir_cadastro_rapido)

        barra.addWidget(self.bt_buscar)
        barra.addWidget(self.bt_pagar)
        barra.addWidget(self.bt_adicionar)

        layout.addLayout(barra)

        # ======================
        # ATALHOS DE TECLADO
        # ======================

        contexto = Qt.WidgetWithChildrenShortcut

        self.atalho_f1 = QShortcut(QKeySequence("F1"), self)
        self.atalho_f1.setContext(contexto)
        self.atalho_f1.activated.connect(self.abrir_busca)

        self.atalho_f4 = QShortcut(QKeySequence("F4"), self)
        self.atalho_f4.setContext(contexto)
        self.atalho_f4.activated.connect(self.abrir_cadastro_rapido)

    # ==================================================
    # BUSCAR PRODUTO (F1) - abre o modal de pesquisa
    # ==================================================

    def abrir_busca(self):

        dialog = BuscarProdutoDialog(self)
        dialog.produto_selecionado.connect(
            self.adicionar_produto_ao_carrinho
        )
        dialog.exec()

    def adicionar_produto_ao_carrinho(self, produto, quantidade):

        encontrou = False

        for item in self.itens:

            if item["id"] == produto["id"]:

                item["quantidade"] += quantidade

                encontrou = True

                break

        if not encontrou:

            self.itens.append(
                {
                    "id": produto["id"],
                    "codigo": produto["codigo"],
                    "nome": produto["nome"],
                    "preco": float(produto["preco"]),
                    "quantidade": quantidade,
                }
            )

        self.atualizar_tabela()

    # ==================================================
    # ADICIONAR PRODUTO (F4) - cadastro rápido sem sair do PDV
    # ==================================================

    def abrir_cadastro_rapido(self):

        dialog = CadastroRapidoDialog(self)

        if dialog.exec() != QDialog.Accepted:
            return

        if not dialog.produto_criado:
            return

        codigo = (
            dialog.produto_criado.get("codigo_barras")
            or dialog.produto_criado.get("codigo")
        )

        produto = buscar_produto(codigo)

        if produto is None:
            return

        self.adicionar_produto_ao_carrinho(produto, 1)

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

            self.tabela.setCellWidget(
                linha,
                2,
                self.criar_widget_qtde(linha, item["quantidade"])
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

            self.tabela.setCellWidget(
                linha,
                5,
                self.criar_widget_excluir(linha)
            )

        self.lbl_itens_valor.setText(str(len(self.itens)))

        self.total.setText(
            f"R$ {total:.2f}"
        )

    # ==================================================
    # WIDGETS DE QUANTIDADE / EXCLUIR (por linha)
    # ==================================================

    def criar_widget_qtde(self, linha, quantidade):

        widget = QWidget()

        caixa = QHBoxLayout(widget)
        caixa.setContentsMargins(4, 2, 4, 2)
        caixa.setSpacing(4)

        estilo_botao = """
            QPushButton {
                background:#f0f0f0;
                border-radius:4px;
                font-weight:bold;
            }
            QPushButton:hover {
                background:#e0e0e0;
            }
        """

        bt_menos = QPushButton("-")
        bt_menos.setFixedSize(24, 24)
        bt_menos.setStyleSheet(estilo_botao)
        bt_menos.clicked.connect(
            lambda: self.alterar_quantidade(linha, -1)
        )

        lbl_qtde = QLabel(str(quantidade))
        lbl_qtde.setAlignment(Qt.AlignCenter)
        lbl_qtde.setFixedWidth(24)
        lbl_qtde.setStyleSheet(
            "background:transparent; color:#202225; font-weight:bold;"
        )

        bt_mais = QPushButton("+")
        bt_mais.setFixedSize(24, 24)
        bt_mais.setStyleSheet(estilo_botao)
        bt_mais.clicked.connect(
            lambda: self.alterar_quantidade(linha, 1)
        )

        caixa.addWidget(bt_menos)
        caixa.addWidget(lbl_qtde)
        caixa.addWidget(bt_mais)
        caixa.addStretch()

        return widget

    def criar_widget_excluir(self, linha):

        widget = QWidget()

        caixa = QHBoxLayout(widget)
        caixa.setContentsMargins(0, 0, 0, 0)

        bt_excluir = QPushButton("🗑")
        bt_excluir.setFixedSize(28, 28)
        bt_excluir.setCursor(Qt.PointingHandCursor)
        bt_excluir.setStyleSheet("""
            QPushButton {
                background:transparent;
                border:none;
                font-size:14px;
            }
            QPushButton:hover {
                background:#fdecea;
                border-radius:6px;
            }
        """)
        bt_excluir.clicked.connect(
            lambda: self.remover_item(linha)
        )

        caixa.addWidget(bt_excluir)

        return widget

    def alterar_quantidade(self, linha, delta):

        if linha >= len(self.itens):
            return

        nova_quantidade = self.itens[linha]["quantidade"] + delta

        if nova_quantidade <= 0:
            self.remover_item(linha)
            return

        self.itens[linha]["quantidade"] = nova_quantidade

        self.atualizar_tabela()

    def remover_item(self, linha):

        if linha >= len(self.itens):
            return

        del self.itens[linha]

        self.atualizar_tabela()

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

        self.limpar_venda()

    def limpar_venda(self):

        self.itens.clear()

        self.tabela.setRowCount(0)

        self.lbl_itens_valor.setText("0")

        self.total.setText("R$ 0,00")

    # ==================================================
    # FINALIZAR VENDA (PAGAR - F3)
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

        tela = PagamentoWindow(total, self.itens)

        if tela.exec() != QDialog.Accepted:
            return

        try:

            response = enviar_venda(
                itens=self.itens,
                forma_pagamento=tela.forma_pagamento,
                cliente_id=tela.cliente_id,
                desconto=0,
                observacao=None,
                data_vencimento=None,
                forma_pagamento_2=tela.forma_pagamento_2,
                valor_forma_2=(
                    tela.valor_forma_2 if tela.forma_pagamento_2 else None
                ),
            )

            if response.status_code == 201:

                concluida = VendaConcluidaDialog(
                    total,
                    self.itens,
                    tela.forma_pagamento,
                    cliente_nome=tela.cliente_nome,
                    forma_pagamento_2=tela.forma_pagamento_2,
                    valor_forma_2=tela.valor_forma_2,
                    parent=self,
                )
                concluida.exec()

                self.limpar_venda()

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
