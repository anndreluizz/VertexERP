import csv
from datetime import date, datetime

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QFont, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QDateEdit,
    QPushButton,
    QFrame,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from services import api
from services.produto_service import listar_produtos
from services.venda_service import listar_vendas
from services.movimento_fiado_service import (
    saldo_cliente,
    listar_movimentos_cliente,
    registrar_pagamento,
    lancar_fiado_manual,
)

from design import tokens
from design.icons import icone
from design.widgets import (
    Avatar,
    Badge,
    BotaoPerigo,
    BotaoPrimario,
    BotaoSecundario,
    BotaoSucesso,
    CampoTexto,
    Card,
    SecaoCard,
)


FORMAS_PAGAMENTO = [
    ("Dinheiro", "DINHEIRO"),
    ("PIX", "PIX"),
    ("Cartão", "CARTAO"),
    ("Transferência", "TRANSFERENCIA"),
    ("Cheque", "CHEQUE"),
]

NOMES_FORMA_FIADO = {valor: rotulo for rotulo, valor in FORMAS_PAGAMENTO}


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


class LancarFiadoDialog(QDialog):
    """Lançamento manual de uma compra fiada — pensado pra migrar o
    saldo que já existia nas fichas de papel (caderninho tradicional),
    onde a loja quer registrar o valor e os itens sem precisar recriar
    a venda inteira no PDV."""

    def __init__(self, cliente, parent=None):

        super().__init__(parent)

        self.cliente = cliente

        self.setWindowTitle("Lançar Fiado")
        self.setFixedSize(420, 460)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        titulo = QLabel("Lançar Fiado")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            f"Registra uma compra fiada de {cliente['nome']} — "
            "use pra colocar no sistema o saldo que já estava "
            "anotado na ficha de papel."
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(6)

        lbl_valor_titulo = QLabel("VALOR (R$)")
        lbl_valor_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.valor = QLineEdit()
        self.valor.setPlaceholderText("0,00")
        self.valor.setAlignment(Qt.AlignCenter)
        self.valor.setStyleSheet(f"""
            QLineEdit {{
                font-size:32px; font-weight:800; color:{tokens.ERRO};
                border:none; border-bottom:2px solid {tokens.BORDA};
                padding:6px 0; background:transparent;
            }}
        """)

        layout.addWidget(lbl_valor_titulo)
        layout.addWidget(self.valor)

        lbl_itens_titulo = QLabel("DESCRIÇÃO (ITENS COMPRADOS)")
        lbl_itens_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.itens = CampoTexto("Ex: mochila, caderno")

        layout.addWidget(lbl_itens_titulo)
        layout.addWidget(self.itens)

        lbl_data_titulo = QLabel("DATA DA COMPRA")
        lbl_data_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.data = QDateEdit()
        self.data.setCalendarPopup(True)
        self.data.setDisplayFormat("dd/MM/yyyy")
        self.data.setDate(QDate.currentDate())
        self.data.setMinimumHeight(44)
        self.data.setStyleSheet(f"""
            QDateEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
            }}
            QDateEdit:focus {{ border: 1.5px solid {tokens.ERRO}; }}
        """)

        layout.addWidget(lbl_data_titulo)
        layout.addWidget(self.data)

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.clicked.connect(self.reject)

        bt_confirmar = BotaoPerigo("Salvar")
        bt_confirmar.setMinimumHeight(46)
        bt_confirmar.setAutoDefault(False)
        bt_confirmar.clicked.connect(self.confirmar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(bt_confirmar)

        layout.addLayout(botoes)

        self.valor.setFocus()

    def confirmar(self):

        try:
            valor = float(self.valor.text().replace(",", "."))
        except ValueError:
            QMessageBox.warning(
                self, "Atenção", "Informe um valor válido."
            )
            return

        if valor <= 0:
            QMessageBox.warning(
                self, "Atenção", "Informe um valor maior que zero."
            )
            return

        itens = self.itens.text().strip() or None

        data_qt = self.data.date()
        data_iso = (
            date(data_qt.year(), data_qt.month(), data_qt.day())
            .isoformat()
            + "T00:00:00"
        )

        response = lancar_fiado_manual(
            self.cliente["id"], valor, itens, data_iso
        )

        if response.status_code in (200, 201):
            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))


class RegistrarPagamentoDialog(QDialog):

    def __init__(self, cliente, saldo_devedor, parent=None):

        super().__init__(parent)

        self.cliente = cliente
        self.forma_pagamento = "DINHEIRO"

        self.setWindowTitle("Registrar Pagamento")
        self.setFixedSize(420, 560)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        titulo = QLabel("Registrar Pagamento")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            f"Saldo devedor de {cliente['nome']}: "
            f"{_formatar_moeda(saldo_devedor)}"
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(6)

        lbl_valor_titulo = QLabel("VALOR A PAGAR (R$)")
        lbl_valor_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.valor = QLineEdit()
        self.valor.setText(f"{saldo_devedor:.2f}")
        self.valor.setAlignment(Qt.AlignCenter)
        self.valor.setStyleSheet(f"""
            QLineEdit {{
                font-size:32px; font-weight:800; color:{tokens.SECUNDARIA};
                border:none; border-bottom:2px solid {tokens.BORDA};
                padding:6px 0; background:transparent;
            }}
        """)

        layout.addWidget(lbl_valor_titulo)
        layout.addWidget(self.valor)

        lbl_forma_titulo = QLabel("FORMA DE PAGAMENTO")
        lbl_forma_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(lbl_forma_titulo)

        formas_layout = QGridLayout()
        formas_layout.setSpacing(8)

        self.botoes_forma = {}

        for indice, (rotulo, valor) in enumerate(FORMAS_PAGAMENTO):

            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setAutoDefault(False)
            bt.setMinimumHeight(44)
            bt.clicked.connect(
                lambda checked, v=valor: self.selecionar_forma(v)
            )

            self.botoes_forma[valor] = bt
            formas_layout.addWidget(bt, indice // 3, indice % 3)

        layout.addLayout(formas_layout)

        lbl_obs_titulo = QLabel("OBSERVAÇÃO (OPCIONAL)")
        lbl_obs_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.observacao = CampoTexto("Ex: pagamento parcial, combinado...")

        layout.addWidget(lbl_obs_titulo)
        layout.addWidget(self.observacao)

        lbl_data_titulo = QLabel("DATA DO PAGAMENTO")
        lbl_data_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.data = QDateEdit()
        self.data.setCalendarPopup(True)
        self.data.setDisplayFormat("dd/MM/yyyy")
        self.data.setDate(QDate.currentDate())
        self.data.setMinimumHeight(44)
        self.data.setStyleSheet(f"""
            QDateEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
            }}
            QDateEdit:focus {{ border: 1.5px solid {tokens.SECUNDARIA}; }}
        """)

        layout.addWidget(lbl_data_titulo)
        layout.addWidget(self.data)

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.clicked.connect(self.reject)

        self.bt_confirmar = BotaoSucesso("Confirmar")
        self.bt_confirmar.setMinimumHeight(46)
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.clicked.connect(self.confirmar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(self.bt_confirmar)

        layout.addLayout(botoes)

        self.selecionar_forma("DINHEIRO")

    def selecionar_forma(self, valor):

        self.forma_pagamento = valor

        for chave, botao in self.botoes_forma.items():

            selecionado = chave == valor

            botao.setChecked(selecionado)

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.SECUNDARIA if selecionado else tokens.FUNDO};
                    color: {"white" if selecionado else tokens.TEXTO};
                    border-radius: {tokens.RADIUS_SM}px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background: {tokens.SECUNDARIA_HOVER if selecionado else tokens.BORDA};
                }}
            """)

    def confirmar(self):

        try:
            valor = float(self.valor.text().replace(",", "."))
        except ValueError:
            QMessageBox.warning(
                self, "Atenção", "Informe um valor válido."
            )
            return

        if valor <= 0:
            QMessageBox.warning(
                self, "Atenção", "Informe um valor maior que zero."
            )
            return

        data_qt = self.data.date()
        data_iso = (
            date(data_qt.year(), data_qt.month(), data_qt.day())
            .isoformat()
            + "T00:00:00"
        )

        response = registrar_pagamento(
            self.cliente["id"],
            valor,
            self.forma_pagamento,
            descricao=self.observacao.text().strip() or None,
            data=data_iso,
        )

        if response.status_code in (200, 201):
            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))


class FichaClienteDialog(QDialog):

    def __init__(self, cliente, parent=None):

        super().__init__(parent)

        self.cliente = cliente
        self._vendas_por_id = {}
        self._nomes_produto = {}
        self._movimentos = []

        self.setWindowTitle(f"Ficha - {cliente['nome']}")
        self.resize(960, 720)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        raiz.addWidget(self._construir_cabecalho())

        corpo = QHBoxLayout()
        corpo.setContentsMargins(24, 20, 24, 16)
        corpo.setSpacing(16)

        coluna_esquerda = QVBoxLayout()
        coluna_esquerda.setSpacing(16)

        coluna_esquerda.addWidget(self._construir_card_financeiro())
        coluna_esquerda.addLayout(self._construir_botoes_acao())
        coluna_esquerda.addWidget(self._construir_abas(), stretch=1)

        corpo.addLayout(coluna_esquerda, stretch=2)
        corpo.addWidget(self._construir_painel_lateral())

        raiz.addLayout(corpo, stretch=1)
        raiz.addWidget(self._construir_rodape())

        self.carregar()

    # ======================================
    # CONSTRUÇÃO DA INTERFACE
    # ======================================

    def _construir_cabecalho(self):

        cabecalho = QFrame()
        cabecalho.setStyleSheet(f"background:{tokens.SIDEBAR};")

        layout = QHBoxLayout(cabecalho)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(16)

        self.avatar = Avatar(self.cliente.get("nome", ""), tamanho=56)
        layout.addWidget(self.avatar)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(2)

        linha_nome = QHBoxLayout()
        linha_nome.setSpacing(10)

        self.lbl_titulo = QLabel(self.cliente["nome"])
        self.lbl_titulo.setStyleSheet(f"""
            background:transparent; color:white;
            font-size:{tokens.TAMANHO_XXL}px; font-weight:800;
        """)

        self.badge_ativo = Badge("Ativo", "sucesso")

        linha_nome.addWidget(self.lbl_titulo)
        linha_nome.addWidget(self.badge_ativo, 0)
        linha_nome.addStretch()

        self.lbl_subtitulo = QLabel()
        self.lbl_subtitulo.setWordWrap(True)
        self.lbl_subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SIDEBAR};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        col_texto.addLayout(linha_nome)
        col_texto.addWidget(self.lbl_subtitulo)

        layout.addLayout(col_texto, stretch=1)

        self._atualizar_cabecalho(self.cliente)

        return cabecalho

    def _construir_card_financeiro(self):

        self.card_financeiro = Card()

        layout = QHBoxLayout(self.card_financeiro)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(28)

        col_saldo = QVBoxLayout()
        col_saldo.setSpacing(2)

        lbl_saldo_titulo = QLabel("SALDO DEVEDOR (FIADO)")
        lbl_saldo_titulo.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.lbl_saldo_valor = QLabel("R$ 0,00")
        self.lbl_saldo_valor.setStyleSheet(f"""
            background:transparent; border:none; font-size:32px;
            font-weight:800; color:{tokens.ERRO};
        """)

        self.lbl_saldo_info = QLabel("")
        self.lbl_saldo_info.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        col_saldo.addWidget(lbl_saldo_titulo)
        col_saldo.addWidget(self.lbl_saldo_valor)
        col_saldo.addWidget(self.lbl_saldo_info)

        layout.addLayout(col_saldo)

        linha = QFrame()
        linha.setFixedWidth(1)
        linha.setStyleSheet(f"background:{tokens.BORDA};")
        layout.addWidget(linha)

        grid_stats = QGridLayout()
        grid_stats.setHorizontalSpacing(28)
        grid_stats.setVerticalSpacing(6)

        self.lbl_total_comprado = self._stat_pequena(
            grid_stats, 0, 0, "TOTAL COMPRADO"
        )
        self.lbl_qtd_compras = self._stat_pequena(
            grid_stats, 0, 1, "QTD. COMPRAS"
        )
        self.lbl_ultima_compra = self._stat_pequena(
            grid_stats, 0, 2, "ÚLTIMA COMPRA"
        )
        self.lbl_ultimo_pagamento = self._stat_pequena(
            grid_stats, 1, 0, "ÚLTIMO PAGAMENTO"
        )
        self.lbl_cliente_desde = self._stat_pequena(
            grid_stats, 1, 1, "CLIENTE DESDE*"
        )

        layout.addLayout(grid_stats, stretch=1)

        return self.card_financeiro

    def _stat_pequena(self, grid, linha, coluna, titulo):

        col = QVBoxLayout()
        col.setSpacing(0)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        lbl_valor = QLabel("—")
        lbl_valor.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_MD}px;
            font-weight:700; color:{tokens.TEXTO};
        """)

        col.addWidget(lbl_titulo)
        col.addWidget(lbl_valor)

        grid.addLayout(col, linha, coluna)

        return lbl_valor

    def _construir_botoes_acao(self):

        layout = QHBoxLayout()
        layout.setSpacing(10)

        self.bt_lancar_fiado = BotaoPerigo("Lançar Fiado", icone_nome="plus")
        self.bt_lancar_fiado.setMinimumHeight(46)
        self.bt_lancar_fiado.setAutoDefault(False)
        self.bt_lancar_fiado.clicked.connect(self.lancar_fiado)

        self.bt_pagar = BotaoSucesso("Registrar Pagamento", icone_nome="check")
        self.bt_pagar.setMinimumHeight(46)
        self.bt_pagar.setAutoDefault(False)
        self.bt_pagar.clicked.connect(self.registrar_pagamento)

        self.bt_extrato = BotaoSecundario("Imprimir Extrato", icone_nome="printer")
        self.bt_extrato.setMinimumHeight(46)
        self.bt_extrato.setAutoDefault(False)
        self.bt_extrato.clicked.connect(self.imprimir_extrato)

        self.bt_csv = BotaoSecundario("Exportar CSV", icone_nome="download")
        self.bt_csv.setMinimumHeight(46)
        self.bt_csv.setAutoDefault(False)
        self.bt_csv.clicked.connect(self.exportar_csv)

        layout.addWidget(self.bt_lancar_fiado)
        layout.addWidget(self.bt_pagar)
        layout.addStretch()
        layout.addWidget(self.bt_extrato)
        layout.addWidget(self.bt_csv)

        return layout

    def _construir_abas(self):

        container = QFrame()
        container.setStyleSheet("background:transparent;")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        abas_layout = QHBoxLayout()
        abas_layout.setSpacing(24)

        self.bt_aba_historico = self._botao_aba("Histórico Financeiro")
        self.bt_aba_compras = self._botao_aba("Compras")
        self.bt_aba_pagamentos = self._botao_aba("Pagamentos")
        self.bt_aba_observacoes = self._botao_aba("Observações")

        self.bt_aba_historico.clicked.connect(lambda: self._selecionar_aba(0))
        self.bt_aba_compras.clicked.connect(lambda: self._selecionar_aba(1))
        self.bt_aba_pagamentos.clicked.connect(lambda: self._selecionar_aba(2))
        self.bt_aba_observacoes.clicked.connect(lambda: self._selecionar_aba(3))

        self.botoes_aba = [
            self.bt_aba_historico,
            self.bt_aba_compras,
            self.bt_aba_pagamentos,
            self.bt_aba_observacoes,
        ]

        for botao in self.botoes_aba:
            abas_layout.addWidget(botao)

        abas_layout.addStretch()

        layout.addLayout(abas_layout)

        linha_abas = QFrame()
        linha_abas.setFixedHeight(1)
        linha_abas.setStyleSheet(f"background:{tokens.BORDA};")
        layout.addWidget(linha_abas)

        layout.addSpacing(12)

        self.tabela_historico = self._construir_tabela()
        self.tabela_compras = self._construir_tabela()
        self.tabela_pagamentos = self._construir_tabela()
        self.pagina_observacoes = self._construir_pagina_observacoes()

        self.paginas_aba = [
            self.tabela_historico,
            self.tabela_compras,
            self.tabela_pagamentos,
            self.pagina_observacoes,
        ]

        for pagina in self.paginas_aba:
            layout.addWidget(pagina, stretch=1)

        self._selecionar_aba(0)

        return container

    def _botao_aba(self, texto):

        botao = QPushButton(texto)
        botao.setCheckable(True)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:700; padding-bottom:10px;
            }}
            QPushButton:checked {{
                color:{tokens.PRIMARIA}; border-bottom:2px solid {tokens.PRIMARIA};
            }}
        """)
        return botao

    def _selecionar_aba(self, indice):

        for i, botao in enumerate(self.botoes_aba):
            botao.setChecked(i == indice)

        for i, pagina in enumerate(self.paginas_aba):
            pagina.setVisible(i == indice)

    def _construir_pagina_observacoes(self):

        pagina = QFrame()
        pagina.setStyleSheet("background:transparent;")

        layout = QVBoxLayout(pagina)
        layout.setAlignment(Qt.AlignCenter)

        lbl = QLabel(
            "Observações por cliente ainda estão em desenvolvimento."
        )
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_BASE}px;
        """)

        layout.addWidget(lbl)

        return pagina

    def _construir_tabela(self):

        tabela = QTableWidget()
        tabela.setColumnCount(6)
        tabela.setHorizontalHeaderLabels(
            ["", "Data", "Descrição", "Forma Pagamento", "Valor", "Saldo Após"]
        )
        tabela.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        tabela.setColumnWidth(0, 36)
        tabela.setColumnWidth(1, 140)
        tabela.setColumnWidth(3, 140)
        tabela.setColumnWidth(4, 110)
        tabela.setColumnWidth(5, 110)
        tabela.verticalHeader().setVisible(False)
        tabela.verticalHeader().setDefaultSectionSize(38)
        tabela.setAlternatingRowColors(True)
        tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        tabela.setSelectionMode(QTableWidget.NoSelection)
        tabela.setFocusPolicy(Qt.NoFocus)
        tabela.setShowGrid(False)
        tabela.setStyleSheet(f"""
            QTableWidget {{
                background:{tokens.CARD};
                alternate-background-color:{tokens.FUNDO};
                border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_MD}px;
                color:{tokens.TEXTO};
                font-size:{tokens.TAMANHO_BASE}px;
            }}
            QTableWidget::item {{
                background:transparent;
            }}
            QHeaderView::section {{
                background:{tokens.FUNDO};
                color:{tokens.TEXTO_SECUNDARIO};
                padding:8px;
                border:none;
                border-bottom:1px solid {tokens.BORDA};
                font-weight:700;
                font-size:{tokens.TAMANHO_XS}px;
            }}
        """)

        return tabela

    def _construir_painel_lateral(self):

        self.painel_lateral = SecaoCard("Resumo", "bar-chart-2")
        self.painel_lateral.setFixedWidth(260)

        self.lbl_resumo_total_comprado = self._linha_resumo(
            self.painel_lateral, "Total Comprado"
        )
        self.lbl_resumo_total_pago = self._linha_resumo(
            self.painel_lateral, "Total Pago"
        )
        self.lbl_resumo_saldo_atual = self._linha_resumo(
            self.painel_lateral, "Saldo Atual"
        )
        self.lbl_resumo_maior_compra = self._linha_resumo(
            self.painel_lateral, "Maior Compra"
        )
        self.lbl_resumo_ultima_compra = self._linha_resumo(
            self.painel_lateral, "Última Compra"
        )
        self.lbl_resumo_ticket_medio = self._linha_resumo(
            self.painel_lateral, "Ticket Médio"
        )
        self.lbl_resumo_total_compras = self._linha_resumo(
            self.painel_lateral, "Total de Compras"
        )

        self.painel_lateral.corpo.addStretch()

        return self.painel_lateral

    def _linha_resumo(self, secao, titulo):

        linha = QVBoxLayout()
        linha.setSpacing(0)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        lbl_valor = QLabel("—")
        lbl_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:700;
        """)

        linha.addWidget(lbl_titulo)
        linha.addWidget(lbl_valor)

        secao.corpo.addLayout(linha)

        return lbl_valor

    def _construir_rodape(self):

        rodape = QFrame()
        rodape.setStyleSheet(f"""
            background:{tokens.CARD}; border-top:1px solid {tokens.BORDA};
        """)

        layout = QHBoxLayout(rodape)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(10)

        bt_editar = BotaoPrimario("Editar Cliente", icone_nome="edit-2")
        bt_editar.setMinimumHeight(42)
        bt_editar.setAutoDefault(False)
        bt_editar.clicked.connect(self.editar_cliente)

        bt_excluir = BotaoPerigo("Excluir", icone_nome="trash-2")
        bt_excluir.setMinimumHeight(42)
        bt_excluir.setAutoDefault(False)
        bt_excluir.clicked.connect(self.excluir_cliente_atual)

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.setMinimumHeight(42)
        bt_fechar.setAutoDefault(False)
        bt_fechar.clicked.connect(self.accept)

        layout.addWidget(bt_editar)
        layout.addWidget(bt_excluir)
        layout.addStretch()
        layout.addWidget(bt_fechar)

        return rodape

    # ======================================
    # DADOS
    # ======================================

    def _atualizar_cabecalho(self, cliente):

        self.lbl_titulo.setText(cliente["nome"])

        ativo = cliente.get("ativo", True)
        self.badge_ativo.setText("Ativo" if ativo else "Inativo")
        variante = "sucesso" if ativo else "erro"
        fundo, cor_texto = Badge.VARIANTES[variante]
        self.badge_ativo.setStyleSheet(f"""
            background: {fundo}; color: {cor_texto};
            border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
            font-weight: 600; padding: 3px 10px;
        """)

        detalhes = " · ".join(
            filter(
                None,
                [
                    cliente.get("telefone"),
                    cliente.get("cpf_cnpj"),
                    cliente.get("endereco"),
                ],
            )
        ) or "Sem dados de contato"

        self.lbl_subtitulo.setText(detalhes)

    def editar_cliente(self):

        from telas.cadastro_cliente import CadastroClienteDialog

        dialogo = CadastroClienteDialog(self.cliente, parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        if dialogo.cliente_salvo:
            self.cliente = dialogo.cliente_salvo
            self._atualizar_cabecalho(self.cliente)

    def excluir_cliente_atual(self):

        from services.cliente_service import excluir_cliente

        resposta = QMessageBox.question(
            self,
            "Excluir Cliente",
            f"Deseja desativar o cliente\n\n{self.cliente['nome']} ?"
        )

        if resposta != QMessageBox.Yes:
            return

        response = excluir_cliente(self.cliente["id"])

        if response.status_code == 200:
            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def _descricao_com_itens(self, mov):
        """Pra compras vindas de uma venda de verdade do PDV, troca o
        texto generico ("Venda #12") pela lista dos produtos —
        exatamente o que aparecia escrito a mao na ficha de papel.
        Lancamentos manuais (sem venda_id) ja tem os itens digitados
        direto na descricao, entao ficam como estao."""

        venda_id = mov.get("venda_id")
        descricao = mov.get("descricao") or ""

        if mov.get("tipo") != "COMPRA" or venda_id is None:
            return descricao

        venda = self._vendas_por_id.get(venda_id)

        if not venda or not venda.get("itens"):
            return descricao

        partes = []

        for item in venda["itens"]:
            nome = self._nomes_produto.get(
                item.get("produto_id"), "Produto removido"
            )
            quantidade = item.get("quantidade", 1)
            partes.append(f"{nome} x{quantidade}")

        return ", ".join(partes) if partes else descricao

    @staticmethod
    def _e_estorno(mov):
        return (mov.get("descricao") or "").startswith("Estorno")

    def carregar(self):

        saldo = saldo_cliente(self.cliente["id"])

        self.lbl_saldo_valor.setText(_formatar_moeda(saldo))
        self.lbl_saldo_valor.setStyleSheet(f"""
            background:transparent; border:none; font-size:32px;
            font-weight:800;
            color:{tokens.ERRO if saldo > 0 else tokens.SECUNDARIA};
        """)

        self.bt_pagar.setEnabled(saldo > 0)

        self._vendas_por_id = {
            v["id"]: v for v in listar_vendas()
        }
        self._nomes_produto = {
            p["id"]: p["nome"] for p in listar_produtos()
        }

        movimentos = listar_movimentos_cliente(self.cliente["id"])

        # ordem cronologica (mais antigo primeiro) pra calcular o saldo
        # corrido — depois inverte só na hora de exibir
        movimentos_cron = sorted(
            movimentos, key=lambda m: m.get("data", "")
        )

        saldo_corrido = 0.0
        historico_calculado = []

        for mov in movimentos_cron:

            valor = float(mov.get("valor", 0) or 0)

            if mov.get("tipo") == "COMPRA":
                saldo_corrido += valor
            else:
                saldo_corrido -= valor

            historico_calculado.append((mov, saldo_corrido))

        historico_calculado.reverse()

        self._movimentos = historico_calculado

        self._preencher_tabela(self.tabela_historico, historico_calculado)
        self._preencher_tabela(
            self.tabela_compras,
            [h for h in historico_calculado if h[0].get("tipo") == "COMPRA"],
        )
        self._preencher_tabela(
            self.tabela_pagamentos,
            [h for h in historico_calculado if h[0].get("tipo") == "PAGAMENTO"],
        )

        self._atualizar_stats(movimentos_cron, saldo)

    def _preencher_tabela(self, tabela, historico):

        tabela.setRowCount(len(historico))

        for linha, (mov, saldo_apos) in enumerate(historico):

            tipo = mov.get("tipo", "")
            estorno = self._e_estorno(mov)

            if estorno:
                cor = tokens.ERRO
                icone_nome = "refresh-cw"
            elif tipo == "COMPRA":
                cor = tokens.PRIMARIA
                icone_nome = "shopping-cart"
            else:
                cor = tokens.SECUNDARIA
                icone_nome = "check"

            item_icone = QTableWidgetItem()
            item_icone.setIcon(icone(icone_nome, cor=cor, tamanho=16))
            tabela.setItem(linha, 0, item_icone)

            data = str(mov.get("data", ""))
            if "T" in data:
                data = data.replace("T", " ")

            item_data = QTableWidgetItem(data[:19])
            item_data.setForeground(QColor(cor))
            tabela.setItem(linha, 1, item_data)

            item_descricao = QTableWidgetItem(self._descricao_com_itens(mov))
            item_descricao.setForeground(QColor(tokens.TEXTO))
            tabela.setItem(linha, 2, item_descricao)

            forma = mov.get("forma_pagamento")
            texto_forma = NOMES_FORMA_FIADO.get(forma, forma) if forma else "—"
            item_forma = QTableWidgetItem(texto_forma)
            item_forma.setForeground(QColor(tokens.TEXTO_SECUNDARIO))
            tabela.setItem(linha, 3, item_forma)

            valor = float(mov.get("valor", 0) or 0)
            texto_valor = (
                f"+ {_formatar_moeda(valor)}"
                if tipo == "COMPRA"
                else f"- {_formatar_moeda(valor)}"
            )
            item_valor = QTableWidgetItem(texto_valor)
            item_valor.setForeground(QColor(cor))
            tabela.setItem(linha, 4, item_valor)

            item_saldo = QTableWidgetItem(_formatar_moeda(saldo_apos))
            item_saldo.setForeground(QColor(tokens.TEXTO))
            tabela.setItem(linha, 5, item_saldo)

    def _atualizar_stats(self, movimentos_cron, saldo_atual):

        compras = [m for m in movimentos_cron if m.get("tipo") == "COMPRA"]
        pagamentos = [m for m in movimentos_cron if m.get("tipo") == "PAGAMENTO"]

        total_comprado = sum(float(m.get("valor", 0) or 0) for m in compras)
        total_pago = sum(float(m.get("valor", 0) or 0) for m in pagamentos)
        qtd_compras = len(compras)
        maior_compra = max(
            (float(m.get("valor", 0) or 0) for m in compras), default=0
        )
        ticket_medio = total_comprado / qtd_compras if qtd_compras else 0

        ultima_compra = compras[-1] if compras else None
        ultimo_pagamento = pagamentos[-1] if pagamentos else None
        primeiro_movimento = movimentos_cron[0] if movimentos_cron else None

        def _data_curta(mov):
            if not mov:
                return "—"
            data = _parse_data(mov.get("data"))
            return data.strftime("%d/%m/%Y") if data else "—"

        # card financeiro
        self.lbl_total_comprado.setText(_formatar_moeda(total_comprado))
        self.lbl_qtd_compras.setText(str(qtd_compras))
        self.lbl_ultima_compra.setText(_data_curta(ultima_compra))
        self.lbl_ultimo_pagamento.setText(_data_curta(ultimo_pagamento))
        self.lbl_cliente_desde.setText(_data_curta(primeiro_movimento))

        if saldo_atual > 0 and movimentos_cron:
            ultimo = movimentos_cron[-1]
            data_ultimo = _parse_data(ultimo.get("data"))
            if data_ultimo:
                dias = (datetime.now() - data_ultimo).days
                self.lbl_saldo_info.setText(
                    f"Última movimentação há {dias} dia(s)"
                    if dias > 0 else "Movimentação de hoje"
                )
            else:
                self.lbl_saldo_info.setText("")
        else:
            self.lbl_saldo_info.setText("")

        # painel lateral
        self.lbl_resumo_total_comprado.setText(_formatar_moeda(total_comprado))
        self.lbl_resumo_total_pago.setText(_formatar_moeda(total_pago))
        self.lbl_resumo_saldo_atual.setText(_formatar_moeda(saldo_atual))
        self.lbl_resumo_maior_compra.setText(_formatar_moeda(maior_compra))
        self.lbl_resumo_ultima_compra.setText(_data_curta(ultima_compra))
        self.lbl_resumo_ticket_medio.setText(_formatar_moeda(ticket_medio))
        self.lbl_resumo_total_compras.setText(str(qtd_compras))

    def registrar_pagamento(self):

        saldo = saldo_cliente(self.cliente["id"])

        if saldo <= 0:
            QMessageBox.information(
                self,
                "Fiado",
                "Este cliente não tem saldo devedor.",
            )
            return

        dialogo = RegistrarPagamentoDialog(
            self.cliente,
            saldo,
            parent=self,
        )

        if dialogo.exec() != QDialog.Accepted:
            return

        self.carregar()

    def lancar_fiado(self):

        dialogo = LancarFiadoDialog(self.cliente, parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        self.carregar()

    # ======================================
    # EXTRATO (PDF) / EXPORTAR CSV
    # ======================================

    def _montar_html_extrato(self):

        config = api.configuracoes()
        nome_loja = config.get("nome_loja") or "Vertex ERP"
        telefone_loja = config.get("telefone") or ""

        usuario = api.me()
        responsavel = usuario.get("nome") or "—"

        saldo = saldo_cliente(self.cliente["id"])
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")

        linhas_tabela = []

        for mov, saldo_apos in reversed(self._movimentos):

            data = str(mov.get("data", ""))
            if "T" in data:
                data = data.replace("T", " ")[:16]

            tipo = mov.get("tipo")
            valor = float(mov.get("valor", 0) or 0)
            descricao = self._descricao_com_itens(mov)

            debito = _formatar_moeda(valor) if tipo == "COMPRA" else ""
            credito = _formatar_moeda(valor) if tipo == "PAGAMENTO" else ""

            linhas_tabela.append(
                f"<tr>"
                f"<td>{data}</td>"
                f"<td>{descricao}</td>"
                f"<td align='right'>{debito}</td>"
                f"<td align='right'>{credito}</td>"
                f"<td align='right'>{_formatar_moeda(saldo_apos)}</td>"
                f"</tr>"
            )

        linhas_html = "".join(linhas_tabela) or (
            "<tr><td colspan='5' align='center'>"
            "Nenhuma movimentação registrada.</td></tr>"
        )

        return f"""
        <div style="text-align:center;">
            <h2 style="margin-bottom:0;">{nome_loja}</h2>
            <div style="color:#666;">{telefone_loja}</div>
        </div>
        <hr>
        <table width="100%" cellspacing="4">
            <tr><td><b>Cliente:</b></td><td>{self.cliente.get('nome', '')}</td></tr>
            <tr><td><b>CPF/CNPJ:</b></td><td>{self.cliente.get('cpf_cnpj') or '—'}</td></tr>
            <tr><td><b>Telefone:</b></td><td>{self.cliente.get('telefone') or '—'}</td></tr>
            <tr><td><b>Emitido em:</b></td><td>{agora}</td></tr>
        </table>
        <h3>Extrato Financeiro</h3>
        <table width="100%" border="1" cellspacing="0" cellpadding="6">
            <tr style="background:#f0f0f0;">
                <th>Data</th><th>Descrição</th><th>Débito</th>
                <th>Crédito</th><th>Saldo</th>
            </tr>
            {linhas_html}
        </table>
        <hr>
        <table width="100%">
            <tr>
                <td><b>Total Devedor:</b></td>
                <td align="right"><b>{_formatar_moeda(saldo)}</b></td>
            </tr>
            <tr>
                <td>Responsável:</td>
                <td align="right">{responsavel}</td>
            </tr>
        </table>
        """

    def _montar_documento_extrato(self):

        documento = QTextDocument()
        documento.setDefaultFont(QFont(tokens.FONTE_FAMILIA_PADRAO, 10))
        documento.setHtml(self._montar_html_extrato())

        return documento

    def imprimir_extrato(self):

        printer = QPrinter(QPrinter.HighResolution)

        dialogo = QPrintDialog(printer, self)

        if dialogo.exec() != QPrintDialog.Accepted:
            return

        self._montar_documento_extrato().print_(printer)

    def exportar_csv(self):

        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Extrato (CSV)",
            f"extrato_{self.cliente['nome'].replace(' ', '_')}.csv",
            "Arquivo CSV (*.csv)",
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".csv"):
            caminho += ".csv"

        try:
            with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:

                escritor = csv.writer(arquivo, delimiter=";")
                escritor.writerow(
                    ["Data", "Tipo", "Descrição", "Forma Pagamento", "Valor", "Saldo Após"]
                )

                for mov, saldo_apos in reversed(self._movimentos):

                    data = str(mov.get("data", ""))
                    if "T" in data:
                        data = data.replace("T", " ")[:16]

                    forma = mov.get("forma_pagamento")
                    texto_forma = NOMES_FORMA_FIADO.get(forma, forma) if forma else ""

                    escritor.writerow([
                        data,
                        mov.get("tipo", ""),
                        self._descricao_com_itens(mov),
                        texto_forma,
                        f"{float(mov.get('valor', 0) or 0):.2f}",
                        f"{saldo_apos:.2f}",
                    ])

            QMessageBox.information(
                self, "Sucesso", "Extrato exportado com sucesso."
            )

        except OSError as erro:
            QMessageBox.critical(self, "Erro", str(erro))
