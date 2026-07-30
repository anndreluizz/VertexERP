from datetime import datetime

from telas.pagamento import PagamentoWindow
from telas.buscar_produto import BuscarProdutoDialog
from telas.venda_concluida import VendaConcluidaDialog
from telas.cadastro_rapido import CadastroRapidoDialog
from telas.selecionar_cliente import SelecionarClienteDialog
from services.venda_service import finalizar_venda as enviar_venda
from services.pdv_service import buscar_produto
from services.caixa_service import caixa_aberto
from services.api import configuracoes

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QShortcut, QKeySequence, QFont
from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
)

from design import tokens
from design.animations import fade_in
from design.icons import icone, icone_pixmap
from design.widgets import (
    Badge,
    BotaoPerigo,
    BotaoPrimario,
    BotaoSecundario,
    BotaoSucesso,
    CampoTexto,
)


def _formatar_moeda(valor):
    return (
        f"R$ {float(valor):,.2f}".replace(",", "X")
        .replace(".", ",").replace("X", ".")
    )


def _parse_data(texto):
    try:
        return datetime.fromisoformat(texto)
    except (ValueError, TypeError):
        return None


def _parse_valor(texto):
    try:
        return max(0.0, float((texto or "").strip().replace(",", ".") or 0))
    except ValueError:
        return 0.0


class PDV(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.itens = []
        self.cliente_id = None
        self.cliente_nome = None
        self.desconto_valor = 0.0
        self.acrescimo_valor = 0.0

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        layout.addLayout(self._construir_cabecalho())
        layout.addWidget(self._construir_campo_codigo())
        layout.addWidget(self.lbl_status_busca)
        layout.addWidget(self._construir_linha_cliente())
        layout.addWidget(self._construir_tabela(), stretch=1)
        layout.addWidget(self._construir_bloco_ajuste())
        layout.addLayout(self._construir_resumo())
        layout.addLayout(self._construir_barra_atalhos())

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

        self.atalho_esc = QShortcut(QKeySequence("Esc"), self)
        self.atalho_esc.setContext(contexto)
        self.atalho_esc.activated.connect(self.cancelar_venda)

        fade_in(self, duracao=200)

    def showEvent(self, event):
        super().showEvent(event)
        self.atualizar_indicador_caixa()
        self.campo_codigo.setFocus()

    # ==================================================
    # CONSTRUÇÃO DA INTERFACE
    # ==================================================

    def _construir_cabecalho(self):

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(12)

        self.bt_voltar = QPushButton()
        self.bt_voltar.setFixedSize(38, 38)
        self.bt_voltar.setCursor(Qt.PointingHandCursor)
        self.bt_voltar.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
        self.bt_voltar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background: {tokens.FUNDO}; }}
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Frente de Caixa")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)

        config = configuracoes()
        nome_loja = config.get("nome_loja") or ""

        self.lbl_loja = QLabel(nome_loja)
        self.lbl_loja.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(self.lbl_loja)

        self.badge_caixa = Badge("Caixa aberto", "sucesso")

        self.bt_cancelar = BotaoPerigo("Cancelar Venda", icone_nome="x")
        self.bt_cancelar.clicked.connect(self.cancelar_venda)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addLayout(col_titulo)
        cabecalho.addSpacing(4)
        cabecalho.addWidget(self.badge_caixa, alignment=Qt.AlignVCenter)
        cabecalho.addStretch()
        cabecalho.addWidget(self.bt_cancelar)

        return cabecalho

    def _construir_campo_codigo(self):

        container = QFrame()
        container.setFixedHeight(68)
        container.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border: 2px solid {tokens.PRIMARIA};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(14)

        lbl_icone = QLabel()
        lbl_icone.setStyleSheet("background:transparent;")
        lbl_icone.setPixmap(icone_pixmap("shopping-cart", cor=tokens.PRIMARIA, tamanho=26))
        layout.addWidget(lbl_icone)

        self.campo_codigo = QLineEdit()
        self.campo_codigo.setPlaceholderText(
            "Código de barras ou código do produto — pressione Enter"
        )
        self.campo_codigo.setFont(QFont(tokens.FONTE_FAMILIA_PADRAO, 20))
        self.campo_codigo.setStyleSheet(f"""
            QLineEdit {{
                border: none; background: transparent;
                color: {tokens.TEXTO}; font-size: 20px; font-weight: 600;
            }}
        """)
        self.campo_codigo.returnPressed.connect(self.processar_codigo)
        layout.addWidget(self.campo_codigo, stretch=1)

        dica = QLabel("F1 busca por nome")
        dica.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(dica)

        self.lbl_status_busca = QLabel("")
        self.lbl_status_busca.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; padding-left: 4px;
        """)

        return container

    def _construir_linha_cliente(self):

        linha = QFrame()
        linha.setStyleSheet("background:transparent; border:none;")

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        lbl_icone = QLabel()
        lbl_icone.setStyleSheet("background:transparent;")
        lbl_icone.setPixmap(icone_pixmap("users", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        layout.addWidget(lbl_icone)

        self.lbl_cliente = QLabel("Nenhum cliente selecionado")
        self.lbl_cliente.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(self.lbl_cliente)
        layout.addStretch()

        self.bt_limpar_cliente = QPushButton("remover")
        self.bt_limpar_cliente.setCursor(Qt.PointingHandCursor)
        self.bt_limpar_cliente.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.ERRO}; font-size:{tokens.TAMANHO_XS}px;
            }}
        """)
        self.bt_limpar_cliente.clicked.connect(self.limpar_cliente)
        self.bt_limpar_cliente.setVisible(False)
        layout.addWidget(self.bt_limpar_cliente)

        self.bt_selecionar_cliente = BotaoSecundario("Selecionar Cliente", icone_nome="users")
        self.bt_selecionar_cliente.setMinimumHeight(32)
        self.bt_selecionar_cliente.clicked.connect(self.abrir_selecionar_cliente)
        layout.addWidget(self.bt_selecionar_cliente)

        return linha

    def _construir_tabela(self):

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

        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setSelectionMode(QTableWidget.NoSelection)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setShowGrid(False)
        self.tabela.verticalHeader().setDefaultSectionSize(46)

        self.tabela.horizontalHeader().setStretchLastSection(False)
        self.tabela.setColumnWidth(2, 120)
        self.tabela.setColumnWidth(5, 48)
        self.tabela.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
                gridline-color: {tokens.BORDA};
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                font-size: {tokens.TAMANHO_BASE}px;
            }}
            QHeaderView::section {{
                background: {tokens.FUNDO};
                color: {tokens.TEXTO_SECUNDARIO};
                font-weight: 700;
                font-size: {tokens.TAMANHO_XS}px;
                padding: 8px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
            QTableWidget::item {{
                border-bottom: 1px solid {tokens.BORDA};
                padding: 4px;
            }}
        """)

        return self.tabela

    def _construir_bloco_ajuste(self):

        container = QWidget()
        container.setStyleSheet("background:transparent;")

        layout_container = QVBoxLayout(container)
        layout_container.setContentsMargins(0, 0, 0, 0)
        layout_container.setSpacing(8)

        self.bt_alternar_ajuste = QPushButton("+ Desconto ou acréscimo")
        self.bt_alternar_ajuste.setCursor(Qt.PointingHandCursor)
        self.bt_alternar_ajuste.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; text-align:left;
                color:{tokens.PRIMARIA}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:600; padding: 0;
            }}
        """)
        self.bt_alternar_ajuste.clicked.connect(self._alternar_bloco_ajuste)
        layout_container.addWidget(self.bt_alternar_ajuste)

        self.bloco_ajuste = QFrame()
        self.bloco_ajuste.setVisible(False)
        self.bloco_ajuste.setStyleSheet(f"""
            QFrame {{
                background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
            }}
        """)

        ajuste_layout = QHBoxLayout(self.bloco_ajuste)
        ajuste_layout.setContentsMargins(16, 14, 16, 14)
        ajuste_layout.setSpacing(16)

        col_desconto = QVBoxLayout()
        col_desconto.setSpacing(4)
        lbl_desconto = QLabel("DESCONTO (R$)")
        lbl_desconto.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)
        self.campo_desconto = CampoTexto("0,00")
        self.campo_desconto.textChanged.connect(self._recalcular_totais)
        col_desconto.addWidget(lbl_desconto)
        col_desconto.addWidget(self.campo_desconto)

        col_acrescimo = QVBoxLayout()
        col_acrescimo.setSpacing(4)
        lbl_acrescimo = QLabel("ACRÉSCIMO (R$)")
        lbl_acrescimo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)
        self.campo_acrescimo = CampoTexto("0,00")
        self.campo_acrescimo.textChanged.connect(self._recalcular_totais)
        col_acrescimo.addWidget(lbl_acrescimo)
        col_acrescimo.addWidget(self.campo_acrescimo)

        ajuste_layout.addLayout(col_desconto)
        ajuste_layout.addLayout(col_acrescimo)
        ajuste_layout.addStretch()

        layout_container.addWidget(self.bloco_ajuste)

        return container

    def _construir_resumo(self):

        resumo = QHBoxLayout()

        col_itens = QVBoxLayout()
        col_itens.setSpacing(0)

        lbl_itens_titulo = QLabel("ITENS")
        lbl_itens_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        self.lbl_itens_valor = QLabel("0")
        self.lbl_itens_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XXL}px; font-weight:800;
        """)

        col_itens.addWidget(lbl_itens_titulo)
        col_itens.addWidget(self.lbl_itens_valor)

        col_total = QVBoxLayout()
        col_total.setSpacing(0)
        col_total.setAlignment(Qt.AlignRight)

        self.lbl_subtotal_info = QLabel("")
        self.lbl_subtotal_info.setAlignment(Qt.AlignRight)
        self.lbl_subtotal_info.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)
        self.lbl_subtotal_info.setVisible(False)

        self.total = QLabel("R$ 0,00")
        self.total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.total.setStyleSheet(f"""
            background:transparent; font-size: 38px; font-weight: 800;
            color: {tokens.SECUNDARIA};
        """)

        col_total.addWidget(self.lbl_subtotal_info)
        col_total.addWidget(self.total)

        resumo.addLayout(col_itens)
        resumo.addStretch()
        resumo.addLayout(col_total)

        return resumo

    def _construir_barra_atalhos(self):

        barra = QHBoxLayout()
        barra.setSpacing(14)

        self.bt_buscar = BotaoSecundario("Buscar (F1)", icone_nome="search")
        self.bt_buscar.setMinimumHeight(56)

        self.bt_adicionar = BotaoPrimario("Adicionar (F4)", icone_nome="plus")
        self.bt_adicionar.setMinimumHeight(56)

        self.bt_pagar = BotaoSucesso("Pagar (F3)", icone_nome="credit-card")
        self.bt_pagar.setMinimumHeight(56)

        self.bt_buscar.clicked.connect(self.abrir_busca)
        self.bt_pagar.clicked.connect(self.finalizar_venda)
        self.bt_adicionar.clicked.connect(self.abrir_cadastro_rapido)

        barra.addWidget(self.bt_buscar, stretch=1)
        barra.addWidget(self.bt_adicionar, stretch=1)
        barra.addWidget(self.bt_pagar, stretch=2)

        return barra

    # ==================================================
    # INDICADOR DE CAIXA ABERTO
    # ==================================================

    def atualizar_indicador_caixa(self):

        info = caixa_aberto()

        if not info:
            self.badge_caixa.setText("Caixa fechado")
            self.badge_caixa.setStyleSheet(f"""
                background: {tokens.ERRO_CLARO}; color: {tokens.ERRO_HOVER};
                border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
                font-weight: 600; padding: 3px 10px;
            """)
            return

        abertura = _parse_data(info.get("data_abertura"))
        hora_texto = abertura.strftime("%H:%M") if abertura else "—"

        self.badge_caixa.setText(f"Caixa aberto às {hora_texto}")
        self.badge_caixa.setStyleSheet(f"""
            background: {tokens.SUCESSO_CLARO}; color: {tokens.SECUNDARIA_HOVER};
            border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
            font-weight: 600; padding: 3px 10px;
        """)

    # ==================================================
    # CÓDIGO DE BARRAS (campo gigante)
    # ==================================================

    def processar_codigo(self):

        codigo = self.campo_codigo.text().strip()

        if not codigo:
            return

        produto = buscar_produto(codigo)

        if produto is None:
            self._mostrar_status_busca(f"Produto não encontrado: {codigo}", erro=True)
            self.campo_codigo.selectAll()
            return

        self.adicionar_produto_ao_carrinho(produto, 1)
        self.campo_codigo.clear()
        self._mostrar_status_busca(f"Adicionado: {produto['nome']}", erro=False)

    def _mostrar_status_busca(self, texto, erro):

        cor = tokens.ERRO if erro else tokens.SECUNDARIA
        self.lbl_status_busca.setStyleSheet(f"""
            background:transparent; color:{cor};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        self.lbl_status_busca.setText(texto)

        QTimer.singleShot(
            2500,
            lambda: (
                self.lbl_status_busca.setText("")
                if self.lbl_status_busca.text() == texto else None
            ),
        )

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
    # CLIENTE (opcional, vale pra qualquer forma de pagamento)
    # ==================================================

    def abrir_selecionar_cliente(self):

        dialogo = SelecionarClienteDialog(self)
        dialogo.cliente_selecionado.connect(self.definir_cliente)
        dialogo.exec()

    def definir_cliente(self, cliente):

        self.cliente_id = cliente["id"]
        self.cliente_nome = cliente["nome"]

        self.lbl_cliente.setText(cliente["nome"])
        self.lbl_cliente.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        self.bt_limpar_cliente.setVisible(True)

    def limpar_cliente(self):

        self.cliente_id = None
        self.cliente_nome = None

        self.lbl_cliente.setText("Nenhum cliente selecionado")
        self.lbl_cliente.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        self.bt_limpar_cliente.setVisible(False)

    # ==================================================
    # DESCONTO / ACRÉSCIMO
    # ==================================================

    def _alternar_bloco_ajuste(self):
        self.bloco_ajuste.setVisible(not self.bloco_ajuste.isVisible())

    # ==================================================
    # ATUALIZAR TABELA / TOTAIS
    # ==================================================

    def atualizar_tabela(self):

        self.tabela.setRowCount(len(self.itens))

        for linha, item in enumerate(self.itens):
            subtotal = item["preco"] * item["quantidade"]

            self.tabela.setItem(
                linha, 0, QTableWidgetItem(item["codigo"])
            )

            self.tabela.setItem(
                linha, 1, QTableWidgetItem(item["nome"])
            )

            self.tabela.setCellWidget(
                linha, 2, self.criar_widget_qtde(linha, item["quantidade"])
            )

            self.tabela.setItem(
                linha, 3, QTableWidgetItem(_formatar_moeda(item["preco"]))
            )

            self.tabela.setItem(
                linha, 4, QTableWidgetItem(_formatar_moeda(subtotal))
            )

            self.tabela.setCellWidget(
                linha, 5, self.criar_widget_excluir(linha)
            )

        self._recalcular_totais()
        self.campo_codigo.setFocus()

    def _recalcular_totais(self):

        subtotal = sum(item["preco"] * item["quantidade"] for item in self.itens)

        self.desconto_valor = _parse_valor(self.campo_desconto.text())
        self.acrescimo_valor = _parse_valor(self.campo_acrescimo.text())

        total = max(0.0, subtotal - self.desconto_valor + self.acrescimo_valor)

        self.lbl_itens_valor.setText(str(len(self.itens)))
        self.total.setText(_formatar_moeda(total))

        if self.desconto_valor or self.acrescimo_valor:

            partes = [f"Subtotal {_formatar_moeda(subtotal)}"]

            if self.desconto_valor:
                partes.append(f"desconto -{_formatar_moeda(self.desconto_valor)}")

            if self.acrescimo_valor:
                partes.append(f"acréscimo +{_formatar_moeda(self.acrescimo_valor)}")

            self.lbl_subtotal_info.setText("  ·  ".join(partes))
            self.lbl_subtotal_info.setVisible(True)

        else:
            self.lbl_subtotal_info.setVisible(False)

        return total

    # ==================================================
    # WIDGETS DE QUANTIDADE / EXCLUIR (por linha)
    # ==================================================

    def criar_widget_qtde(self, linha, quantidade):

        widget = QWidget()

        caixa = QHBoxLayout(widget)
        caixa.setContentsMargins(4, 2, 4, 2)
        caixa.setSpacing(4)

        estilo_botao = f"""
            QPushButton {{
                background:{tokens.FUNDO};
                border-radius:4px;
                font-weight:bold;
                color:{tokens.TEXTO};
            }}
            QPushButton:hover {{
                background:{tokens.BORDA};
            }}
        """

        bt_menos = QPushButton("-")
        bt_menos.setFixedSize(24, 24)
        bt_menos.setCursor(Qt.PointingHandCursor)
        bt_menos.setStyleSheet(estilo_botao)
        bt_menos.clicked.connect(
            lambda: self.alterar_quantidade(linha, -1)
        )

        lbl_qtde = QLabel(str(quantidade))
        lbl_qtde.setAlignment(Qt.AlignCenter)
        lbl_qtde.setFixedWidth(24)
        lbl_qtde.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO}; font-weight:bold;"
        )

        bt_mais = QPushButton("+")
        bt_mais.setFixedSize(24, 24)
        bt_mais.setCursor(Qt.PointingHandCursor)
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

        bt_excluir = QPushButton()
        bt_excluir.setFixedSize(28, 28)
        bt_excluir.setCursor(Qt.PointingHandCursor)
        bt_excluir.setIcon(icone("trash-2", cor=tokens.TEXTO_TERCIARIO, tamanho=15))
        bt_excluir.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                border:none;
                border-radius:6px;
            }}
            QPushButton:hover {{
                background:{tokens.ERRO_CLARO};
            }}
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

        self.limpar_cliente()

        self.campo_desconto.setText("")
        self.campo_acrescimo.setText("")
        self.bloco_ajuste.setVisible(False)

        self.lbl_itens_valor.setText("0")

        self.total.setText("R$ 0,00")
        self.lbl_subtotal_info.setVisible(False)

        self.campo_codigo.setFocus()

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

        total = self._recalcular_totais()

        tela = PagamentoWindow(
            total,
            self.itens,
            cliente_id=self.cliente_id,
            cliente_nome=self.cliente_nome,
        )

        if tela.exec() != QDialog.Accepted:
            return

        desconto_liquido = self.desconto_valor - self.acrescimo_valor

        try:

            response = enviar_venda(
                itens=self.itens,
                forma_pagamento=tela.forma_pagamento,
                cliente_id=tela.cliente_id,
                desconto=desconto_liquido,
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
