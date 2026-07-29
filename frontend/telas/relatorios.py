from datetime import datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
)

from services.api import configuracoes
from services.venda_service import listar_vendas
from services.produto_service import listar_produtos
from services.caixa_service import historico_caixa
from widgets.card import Card


NOMES_FORMA_PAGAMENTO = {
    "DINHEIRO": "Dinheiro",
    "PIX": "PIX",
    "DEBITO": "Débito",
    "CREDITO": "Crédito",
    "BOLETO": "Boleto",
    "PRAZO": "A Prazo",
}

CORES_FORMA_PAGAMENTO = {
    "DINHEIRO": "#2E7D32",
    "PIX": "#1565C0",
    "DEBITO": "#F9A825",
    "CREDITO": "#8E24AA",
    "BOLETO": "#546E7A",
    "PRAZO": "#C62828",
}


class LinhaBarra(QFrame):
    """Uma linha de 'Nome / valor' com uma barra de progresso simples,
    usada tanto no ranking de produtos quanto no mix de pagamentos."""

    def __init__(self, titulo, subtitulo, valor_texto, percentual, cor):

        super().__init__()

        self.setStyleSheet("QFrame{background:transparent; border:none;}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        topo = QHBoxLayout()

        col_texto = QVBoxLayout()
        col_texto.setSpacing(0)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(
            "font-size:13px; font-weight:bold; color:#202225; "
            "background:transparent;"
        )

        col_texto.addWidget(lbl_titulo)

        if subtitulo:
            lbl_sub = QLabel(subtitulo)
            lbl_sub.setStyleSheet(
                "font-size:11px; color:#9E9E9E; background:transparent;"
            )
            col_texto.addWidget(lbl_sub)

        topo.addLayout(col_texto)
        topo.addStretch()

        lbl_valor = QLabel(valor_texto)
        lbl_valor.setStyleSheet(
            f"font-size:13px; font-weight:bold; color:{cor}; "
            "background:transparent;"
        )

        topo.addWidget(lbl_valor)

        layout.addLayout(topo)

        barra_fundo = QFrame()
        barra_fundo.setFixedHeight(6)
        barra_fundo.setStyleSheet(
            "background:#eeeeee; border-radius:3px; border:none;"
        )

        barra_layout = QHBoxLayout(barra_fundo)
        barra_layout.setContentsMargins(0, 0, 0, 0)

        barra_preenchida = QFrame()
        barra_preenchida.setFixedHeight(6)
        barra_preenchida.setStyleSheet(
            f"background:{cor}; border-radius:3px; border:none;"
        )

        largura_relativa = max(0, min(100, percentual))

        barra_layout.addWidget(barra_preenchida, largura_relativa)
        barra_layout.addStretch(100 - largura_relativa)

        layout.addWidget(barra_fundo)


class PainelSecao(QFrame):

    def __init__(self, icone, titulo):

        super().__init__()

        self.setStyleSheet("""
            QFrame {
                background:white;
                border-radius:12px;
                border:1px solid #eeeeee;
            }
        """)

        self.layout_externo = QVBoxLayout(self)
        self.layout_externo.setContentsMargins(18, 16, 18, 16)
        self.layout_externo.setSpacing(12)

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(8)

        lbl_icone = QLabel(icone)
        lbl_icone.setStyleSheet(
            "font-size:16px; background:transparent; border:none;"
        )

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(
            "font-size:14px; font-weight:bold; color:#202225; "
            "background:transparent; border:none;"
        )

        cabecalho.addWidget(lbl_icone)
        cabecalho.addWidget(lbl_titulo)
        cabecalho.addStretch()

        self.layout_externo.addLayout(cabecalho)

        self.corpo = QVBoxLayout()
        self.corpo.setSpacing(14)

        self.layout_externo.addLayout(self.corpo)

    def limpar_corpo(self):
        while self.corpo.count():
            item = self.corpo.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def adicionar_vazio(self, texto):
        lbl = QLabel(texto)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            "color:#9E9E9E; font-size:12px; background:transparent; "
            "border:none; padding:12px;"
        )
        self.corpo.addWidget(lbl)


class Relatorios(QWidget):

    voltar = Signal()

    PERIODOS = [
        "Hoje",
        "Ontem",
        "Últimos 7 dias",
        "Este mês",
        "Mês anterior",
        "Tudo",
    ]

    def __init__(self):
        super().__init__()

        self.vendas = []
        self.produtos = []
        self.caixas = []

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background:#f4f5f7;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()

        self.bt_voltar = QPushButton("← Voltar")
        self.bt_voltar.setStyleSheet("""
            QPushButton {
                background:transparent;
                color:gray;
                border:none;
                font-size:13px;
            }
            QPushButton:hover {
                color:#202225;
            }
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Relatórios")
        titulo.setStyleSheet(
            "background:transparent; font-size:20px; "
            "font-weight:bold; color:#202225;"
        )

        subtitulo = QLabel("GERENCIAMENTO E INTELIGÊNCIA")
        subtitulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "color:#9E9E9E; font-weight:bold;"
        )

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addSpacing(12)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()

        self.bt_imprimir = QPushButton("🖨  Imprimir Relatório")
        self.bt_imprimir.setStyleSheet("""
            QPushButton {
                background:white;
                color:#202225;
                border:1px solid #dcdcdc;
                border-radius:8px;
                padding:10px 16px;
                font-weight:bold;
            }
            QPushButton:hover {
                border:1px solid #9e9e9e;
            }
        """)

        cabecalho.addWidget(self.bt_imprimir)

        layout.addLayout(cabecalho)

        # ======================
        # ABAS
        # ======================

        abas_layout = QHBoxLayout()
        abas_layout.setSpacing(24)

        self.bt_aba_financeiro = self._botao_aba("Centro Financeiro")
        self.bt_aba_caixa = self._botao_aba("Relatório de Caixa")
        self.bt_aba_estoque = self._botao_aba("Relatório de Estoque")

        self.bt_aba_financeiro.clicked.connect(
            lambda: self._selecionar_aba(0)
        )
        self.bt_aba_caixa.clicked.connect(
            lambda: self._selecionar_aba(1)
        )
        self.bt_aba_estoque.clicked.connect(
            lambda: self._selecionar_aba(2)
        )

        abas_layout.addWidget(self.bt_aba_financeiro)
        abas_layout.addWidget(self.bt_aba_caixa)
        abas_layout.addWidget(self.bt_aba_estoque)
        abas_layout.addStretch()

        layout.addLayout(abas_layout)

        linha_abas = QFrame()
        linha_abas.setFixedHeight(1)
        linha_abas.setStyleSheet("background:#e0e0e0; border:none;")
        layout.addWidget(linha_abas)

        self.botoes_aba = [
            self.bt_aba_financeiro,
            self.bt_aba_caixa,
            self.bt_aba_estoque,
        ]

        # ======================
        # PÁGINAS
        # ======================

        self.pagina_financeiro = self._criar_pagina_financeiro()
        self.pagina_caixa = self._criar_pagina_caixa()
        self.pagina_estoque = self._criar_pagina_estoque()

        layout.addWidget(self.pagina_financeiro)
        layout.addWidget(self.pagina_caixa)
        layout.addWidget(self.pagina_estoque)

        self._selecionar_aba(0)

    def _botao_aba(self, texto):

        botao = QPushButton(texto)
        botao.setCheckable(True)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setStyleSheet("""
            QPushButton {
                background:transparent;
                border:none;
                color:#9E9E9E;
                font-size:13px;
                font-weight:bold;
                padding-bottom:10px;
            }
            QPushButton:checked {
                color:#2E7D32;
                border-bottom:2px solid #2E7D32;
            }
        """)
        return botao

    def _selecionar_aba(self, indice):

        paginas = [
            self.pagina_financeiro,
            self.pagina_caixa,
            self.pagina_estoque,
        ]

        for i, botao in enumerate(self.botoes_aba):
            botao.setChecked(i == indice)

        for i, pagina in enumerate(paginas):
            pagina.setVisible(i == indice)

    # ==========================================
    # PÁGINA: CENTRO FINANCEIRO
    # ==========================================

    def _criar_pagina_financeiro(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(16)

        filtro_layout = QHBoxLayout()

        self.combo_periodo = QComboBox()
        self.combo_periodo.addItems(self.PERIODOS)
        self.combo_periodo.setCurrentText("Este mês")
        self.combo_periodo.setMinimumHeight(36)
        self.combo_periodo.setStyleSheet("""
            QComboBox {
                border:1px solid #dcdcdc;
                border-radius:8px;
                padding:4px 12px;
                background:white;
                color:#202225;
            }
        """)
        self.combo_periodo.currentTextChanged.connect(
            self._atualizar_financeiro
        )

        filtro_layout.addWidget(self.combo_periodo)
        filtro_layout.addStretch()

        layout.addLayout(filtro_layout)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self.card_faturamento = Card("Faturamento Bruto", "R$ 0,00")
        self.card_volume = Card("Volume de Vendas", "0")
        self.card_ticket = Card("Ticket Médio", "R$ 0,00")

        cards_layout.addWidget(self.card_faturamento)
        cards_layout.addWidget(self.card_volume)
        cards_layout.addWidget(self.card_ticket)

        layout.addLayout(cards_layout)

        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(16)

        self.painel_ranking = PainelSecao("📦", "Ranking de Produtos")
        self.painel_mix = PainelSecao("💳", "Mix de Pagamentos")

        grid_layout.addWidget(self.painel_ranking, stretch=1)
        grid_layout.addWidget(self.painel_mix, stretch=1)

        layout.addLayout(grid_layout)
        layout.addStretch()

        return pagina

    def _filtrar_vendas_por_periodo(self):

        periodo = self.combo_periodo.currentText()
        agora = datetime.now()
        hoje = agora.date()

        def data_venda(venda):
            texto = venda.get("data", "")
            try:
                return datetime.fromisoformat(texto).date()
            except (ValueError, TypeError):
                return None

        if periodo == "Hoje":
            inicio = hoje
            fim = hoje
        elif periodo == "Ontem":
            inicio = hoje - timedelta(days=1)
            fim = inicio
        elif periodo == "Últimos 7 dias":
            inicio = hoje - timedelta(days=6)
            fim = hoje
        elif periodo == "Este mês":
            inicio = hoje.replace(day=1)
            fim = hoje
        elif periodo == "Mês anterior":
            primeiro_dia_mes_atual = hoje.replace(day=1)
            fim = primeiro_dia_mes_atual - timedelta(days=1)
            inicio = fim.replace(day=1)
        else:
            return [
                v for v in self.vendas
                if v.get("status") != "CANCELADA"
            ]

        resultado = []

        for venda in self.vendas:

            if venda.get("status") == "CANCELADA":
                continue

            data = data_venda(venda)

            if data is None:
                continue

            if inicio <= data <= fim:
                resultado.append(venda)

        return resultado

    def _atualizar_financeiro(self):

        vendas_periodo = self._filtrar_vendas_por_periodo()

        faturamento = sum(
            float(v.get("valor_total", 0)) for v in vendas_periodo
        )
        volume = len(vendas_periodo)
        ticket_medio = faturamento / volume if volume else 0

        self.card_faturamento.atualizar(
            f"R$ {faturamento:,.2f}".replace(",", "X")
            .replace(".", ",").replace("X", ".")
        )
        self.card_volume.atualizar(str(volume))
        self.card_ticket.atualizar(
            f"R$ {ticket_medio:,.2f}".replace(",", "X")
            .replace(".", ",").replace("X", ".")
        )

        self._atualizar_ranking_produtos(vendas_periodo)
        self._atualizar_mix_pagamentos(vendas_periodo)

    def _atualizar_ranking_produtos(self, vendas_periodo):

        self.painel_ranking.limpar_corpo()

        nomes_produto = {
            p["id"]: p["nome"] for p in self.produtos
        }

        totais_por_produto = {}

        for venda in vendas_periodo:
            for item in venda.get("itens", []):
                produto_id = item.get("produto_id")
                subtotal = float(item.get("subtotal", 0))
                totais_por_produto[produto_id] = (
                    totais_por_produto.get(produto_id, 0) + subtotal
                )

        if not totais_por_produto:
            self.painel_ranking.adicionar_vazio(
                "Nenhuma venda no período selecionado."
            )
            return

        ranking = sorted(
            totais_por_produto.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:10]

        maior_valor = ranking[0][1] if ranking else 1

        for posicao, (produto_id, total) in enumerate(ranking, start=1):

            nome = nomes_produto.get(produto_id, "Produto removido")

            percentual = (
                (total / maior_valor) * 100 if maior_valor else 0
            )

            linha = LinhaBarra(
                f"{posicao}. {nome}",
                None,
                f"R$ {total:,.2f}".replace(",", "X")
                .replace(".", ",").replace("X", "."),
                percentual,
                "#1565C0",
            )

            self.painel_ranking.corpo.addWidget(linha)

    def _atualizar_mix_pagamentos(self, vendas_periodo):

        self.painel_mix.limpar_corpo()

        totais_por_forma = {}

        for venda in vendas_periodo:
            forma = venda.get("forma_pagamento", "DINHEIRO")
            valor = float(venda.get("valor_total", 0))
            totais_por_forma[forma] = (
                totais_por_forma.get(forma, 0) + valor
            )

        total_geral = sum(totais_por_forma.values())

        if not total_geral:
            self.painel_mix.adicionar_vazio(
                "Nenhuma venda no período selecionado."
            )
            return

        formas_ordenadas = sorted(
            totais_por_forma.items(),
            key=lambda item: item[1],
            reverse=True,
        )

        for forma, total in formas_ordenadas:

            percentual = (total / total_geral) * 100

            nome = NOMES_FORMA_PAGAMENTO.get(forma, forma)
            cor = CORES_FORMA_PAGAMENTO.get(forma, "#202225")

            linha = LinhaBarra(
                nome,
                f"{percentual:.1f}% do total",
                f"R$ {total:,.2f}".replace(",", "X")
                .replace(".", ",").replace("X", "."),
                percentual,
                cor,
            )

            self.painel_mix.corpo.addWidget(linha)

    # ==========================================
    # PÁGINA: RELATÓRIO DE CAIXA
    # ==========================================

    def _criar_pagina_caixa(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        titulo = QLabel("Histórico de Caixas")
        titulo.setStyleSheet(
            "font-size:14px; font-weight:bold; color:#202225; "
            "background:transparent;"
        )
        layout.addWidget(titulo)

        self.tabela_caixa = QTableWidget()
        self.tabela_caixa.setColumnCount(4)
        self.tabela_caixa.setHorizontalHeaderLabels([
            "Data Abertura",
            "Valor Inicial",
            "Valor Final",
            "Status",
        ])
        self._estilizar_tabela(self.tabela_caixa)

        layout.addWidget(self.tabela_caixa, stretch=1)

        return pagina

    def _atualizar_caixa(self):

        self.tabela_caixa.setRowCount(0)

        for caixa in self.caixas:

            linha = self.tabela_caixa.rowCount()
            self.tabela_caixa.insertRow(linha)

            data_abertura = caixa.get("data_abertura", "")
            try:
                data_formatada = datetime.fromisoformat(
                    data_abertura
                ).strftime("%d/%m/%Y %H:%M")
            except (ValueError, TypeError):
                data_formatada = data_abertura

            status = caixa.get("status", "")
            saldo_final = caixa.get("saldo_final")

            self.tabela_caixa.setItem(
                linha, 0, QTableWidgetItem(data_formatada)
            )
            self.tabela_caixa.setItem(
                linha, 1,
                QTableWidgetItem(
                    f"R$ {float(caixa.get('saldo_inicial', 0)):,.2f}"
                    .replace(",", "X")
                    .replace(".", ",").replace("X", ".")
                ),
            )
            self.tabela_caixa.setItem(
                linha, 2,
                QTableWidgetItem(
                    "—" if status == "ABERTO" else
                    f"R$ {float(saldo_final or 0):,.2f}"
                    .replace(",", "X")
                    .replace(".", ",").replace("X", ".")
                ),
            )

            item_status = QTableWidgetItem(
                "Em aberto" if status == "ABERTO" else "Fechado"
            )
            self.tabela_caixa.setItem(linha, 3, item_status)

        self.tabela_caixa.setCurrentCell(-1, -1)
        self.tabela_caixa.clearSelection()

    # ==========================================
    # PÁGINA: RELATÓRIO DE ESTOQUE
    # ==========================================

    def _criar_pagina_estoque(self):

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(12)

        filtro_layout = QHBoxLayout()
        filtro_layout.setSpacing(8)

        self.bt_estoque_todos = self._botao_filtro_estoque("Todos os Itens")
        self.bt_estoque_critico = self._botao_filtro_estoque(
            "Estoque Crítico"
        )
        self.bt_estoque_esgotado = self._botao_filtro_estoque("Esgotados")

        self.filtro_estoque_atual = "TODOS"

        self.bt_estoque_todos.clicked.connect(
            lambda: self._filtrar_estoque("TODOS")
        )
        self.bt_estoque_critico.clicked.connect(
            lambda: self._filtrar_estoque("CRITICO")
        )
        self.bt_estoque_esgotado.clicked.connect(
            lambda: self._filtrar_estoque("ESGOTADO")
        )

        filtro_layout.addWidget(self.bt_estoque_todos)
        filtro_layout.addWidget(self.bt_estoque_critico)
        filtro_layout.addWidget(self.bt_estoque_esgotado)
        filtro_layout.addStretch()

        layout.addLayout(filtro_layout)

        self.tabela_estoque = QTableWidget()
        self.tabela_estoque.setColumnCount(5)
        self.tabela_estoque.setHorizontalHeaderLabels([
            "Produto",
            "Categoria",
            "Preço Unit.",
            "Em Estoque",
            "Status",
        ])
        self._estilizar_tabela(self.tabela_estoque)

        layout.addWidget(self.tabela_estoque, stretch=1)

        return pagina

    def _botao_filtro_estoque(self, texto):

        botao = QPushButton(texto)
        botao.setCheckable(True)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setMinimumHeight(34)
        botao.setStyleSheet("""
            QPushButton {
                background:white;
                color:#616161;
                border:1px solid #dcdcdc;
                border-radius:17px;
                padding:0 16px;
                font-size:12px;
                font-weight:bold;
            }
            QPushButton:checked {
                background:#202225;
                color:white;
                border:1px solid #202225;
            }
        """)
        return botao

    def _status_estoque(self, produto):

        estoque = produto.get("estoque", 0)
        minimo = produto.get("estoque_minimo", 0)

        if estoque <= 0:
            return "ESGOTADO"

        if estoque <= minimo:
            return "CRITICO"

        return "NORMAL"

    def _filtrar_estoque(self, filtro):

        self.filtro_estoque_atual = filtro

        self.bt_estoque_todos.setChecked(filtro == "TODOS")
        self.bt_estoque_critico.setChecked(filtro == "CRITICO")
        self.bt_estoque_esgotado.setChecked(filtro == "ESGOTADO")

        self._atualizar_estoque()

    def _atualizar_estoque(self):

        criticos = sum(
            1 for p in self.produtos
            if self._status_estoque(p) == "CRITICO"
        )
        esgotados = sum(
            1 for p in self.produtos
            if self._status_estoque(p) == "ESGOTADO"
        )

        self.bt_estoque_critico.setText(f"Estoque Crítico ({criticos})")
        self.bt_estoque_esgotado.setText(f"Esgotados ({esgotados})")

        filtro = self.filtro_estoque_atual

        if filtro == "TODOS":
            produtos_filtrados = self.produtos
        else:
            produtos_filtrados = [
                p for p in self.produtos
                if self._status_estoque(p) == filtro
            ]

        self.tabela_estoque.setRowCount(0)

        cores_status = {
            "NORMAL": "#2E7D32",
            "CRITICO": "#F9A825",
            "ESGOTADO": "#C62828",
        }

        textos_status = {
            "NORMAL": "Normal",
            "CRITICO": "Crítico",
            "ESGOTADO": "Esgotado",
        }

        for produto in produtos_filtrados:

            linha = self.tabela_estoque.rowCount()
            self.tabela_estoque.insertRow(linha)

            status = self._status_estoque(produto)

            self.tabela_estoque.setItem(
                linha, 0, QTableWidgetItem(produto.get("nome", ""))
            )
            self.tabela_estoque.setItem(
                linha, 1,
                QTableWidgetItem(produto.get("categoria") or "—"),
            )
            self.tabela_estoque.setItem(
                linha, 2,
                QTableWidgetItem(
                    f"R$ {float(produto.get('preco_venda', 0)):,.2f}"
                    .replace(",", "X")
                    .replace(".", ",").replace("X", ".")
                ),
            )
            self.tabela_estoque.setItem(
                linha, 3,
                QTableWidgetItem(str(produto.get("estoque", 0))),
            )

            item_status = QTableWidgetItem(textos_status[status])
            item_status.setForeground(QColor(cores_status[status]))
            self.tabela_estoque.setItem(linha, 4, item_status)

        self.tabela_estoque.setCurrentCell(-1, -1)
        self.tabela_estoque.clearSelection()

    # ==========================================
    # ESTILO COMPARTILHADO DE TABELA
    # ==========================================

    def _estilizar_tabela(self, tabela):

        tabela.verticalHeader().setDefaultSectionSize(48)
        tabela.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        tabela.setAlternatingRowColors(True)
        tabela.setSelectionBehavior(QTableWidget.SelectRows)
        tabela.setSelectionMode(QTableWidget.SingleSelection)
        tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        # Sem isso, a celula "atual" (current item, independente de
        # selecao de verdade) pinta com a cor de Highlight do tema assim
        # que a tabela e populada, parecendo uma linha selecionada por
        # engano mesmo sem nenhum clique do usuario.
        tabela.setFocusPolicy(Qt.NoFocus)
        tabela.verticalHeader().setVisible(False)
        tabela.setShowGrid(False)
        tabela.horizontalHeader().setStretchLastSection(True)

        tabela.setStyleSheet("""
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

    # ==========================================
    # CARREGAMENTO
    # ==========================================

    def carregar(self):

        self.vendas = listar_vendas()
        self.produtos = listar_produtos()
        self.caixas = historico_caixa()

        self._atualizar_financeiro()
        self._atualizar_caixa()
        self._atualizar_estoque()
