from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
)

from services.api import dashboard
from widgets.cards.card import Card
from widgets.charts.grafico_vendas import GraficoVendas


class Dashboard(QWidget):

    def __init__(self):

        super().__init__()

        layout = QVBoxLayout(self)

        # ==========================================
        # CABEÇALHO
        # ==========================================

        cabecalho = QHBoxLayout()

        titulo = QLabel("DASHBOARD")

        titulo.setStyleSheet("""
            font-size:24px;
            font-weight:bold;
        """)

        self.bt_atualizar = QPushButton("Atualizar")

        self.bt_atualizar.setStyleSheet("""
            QPushButton{
                background:#616161;
                color:white;
                font-weight:bold;
                border:none;
                border-radius:6px;
                padding:8px 16px;
            }
            QPushButton:hover{
                background:#424242;
            }
        """)

        self.bt_atualizar.clicked.connect(
            self.carregar
        )

        cabecalho.addWidget(titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(self.bt_atualizar)

        layout.addLayout(cabecalho)

        # ==========================================
        # GRID DE CARDS
        # ==========================================

        self.grid = QGridLayout()

        self.grid.setSpacing(16)

        layout.addLayout(self.grid)

        # ==========================================
        # GRÁFICO
        # ==========================================

        self.grafico_container = QVBoxLayout()

        layout.addLayout(self.grafico_container)

        self.carregar()

    # ==========================================
    # CARREGAR DADOS
    # ==========================================

    def carregar(self):

        dados = dashboard()

        self._limpar_grid()
        self._limpar_grafico()

        variacao_vendas = self._variacao(
            dados.get("vendas_hoje", 0), dados.get("vendas_ontem", 0)
        )

        estoque_baixo = dados.get("estoque_baixo", 0)
        cor_estoque = "#C62828" if estoque_baixo > 0 else "#2E7D32"

        self.card_vendas = Card(
            "💰 Vendas Hoje",
            self._moeda(dados.get("vendas_hoje", 0)),
            cor="#2E7D32",
            variacao=variacao_vendas,
            ao_clicar=lambda: self._navegar("vendas"),
        )

        self.card_compras = Card(
            "📥 Compras Hoje",
            self._moeda(dados.get("compras_hoje", 0)),
            cor="#EF6C00",
            ao_clicar=lambda: self._navegar("compras"),
        )

        self.card_caixa = Card(
            "🏦 Saldo Caixa",
            self._moeda(dados.get("saldo_caixa", 0)),
            cor="#1565C0",
            ao_clicar=lambda: self._navegar("caixa"),
        )

        self.card_pagar = Card(
            "📄 Contas a Pagar",
            self._moeda(dados.get("contas_pagar", 0)),
            cor="#C62828",
            ao_clicar=lambda: self._navegar("contas_pagar"),
        )

        self.card_fiado = Card(
            "📒 Devido em Fiado",
            self._moeda(dados.get("total_fiado_devedor", 0)),
            cor="#6A1B9A",
            ao_clicar=lambda: self._navegar("clientes"),
        )

        self.card_estoque_baixo = Card(
            "⚠️ Estoque Baixo",
            str(estoque_baixo),
            cor=cor_estoque,
            ao_clicar=lambda: self._navegar("ajuste_estoque"),
        )

        self.card_clientes = Card(
            "👥 Clientes",
            str(dados.get("clientes", 0)),
            cor="#3949AB",
            ao_clicar=lambda: self._navegar("clientes"),
        )

        self.card_produtos = Card(
            "📦 Produtos",
            str(dados.get("produtos", 0)),
            cor="#8D6E63",
            ao_clicar=lambda: self._navegar("produtos"),
        )

        self.card_fornecedores = Card(
            "🚚 Fornecedores",
            str(dados.get("fornecedores", 0)),
            cor="#37474F",
            ao_clicar=lambda: self._navegar("fornecedores"),
        )

        self.grid.addWidget(self.card_vendas, 0, 0)
        self.grid.addWidget(self.card_compras, 0, 1)
        self.grid.addWidget(self.card_caixa, 0, 2)
        self.grid.addWidget(self.card_pagar, 1, 0)
        self.grid.addWidget(self.card_fiado, 1, 1)
        self.grid.addWidget(self.card_estoque_baixo, 1, 2)
        self.grid.addWidget(self.card_clientes, 2, 0)
        self.grid.addWidget(self.card_produtos, 2, 1)
        self.grid.addWidget(self.card_fornecedores, 2, 2)

        self.grafico = GraficoVendas(dados.get("vendas_ultimos_7_dias", []))
        self.grafico_container.addWidget(self.grafico)

    # ==========================================
    # NAVEGAR PRA OUTRA TELA (CARD CLICÁVEL)
    # ==========================================

    def _navegar(self, nome_pagina):

        principal = self.window()

        pagina = getattr(principal, nome_pagina, None)

        if pagina is not None:
            principal.paginas.setCurrentWidget(pagina)

    # ==========================================
    # VARIAÇÃO PERCENTUAL (HOJE VS ONTEM)
    # ==========================================

    def _variacao(self, hoje, ontem):

        if hoje == 0 and ontem == 0:
            return None

        if ontem == 0:
            return 100.0

        return ((hoje - ontem) / ontem) * 100

    # ==========================================
    # LIMPAR GRID (ANTES DE RECARREGAR)
    # ==========================================

    def _limpar_grid(self):

        while self.grid.count():

            item = self.grid.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    # ==========================================
    # LIMPAR GRÁFICO (ANTES DE RECARREGAR)
    # ==========================================

    def _limpar_grafico(self):

        while self.grafico_container.count():

            item = self.grafico_container.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    # ==========================================
    # FORMATAR VALOR MONETÁRIO
    # ==========================================

    def _moeda(self, valor):

        return f"R$ {float(valor):,.2f}".replace(
            ",", "#"
        ).replace(
            ".", ","
        ).replace(
            "#", "."
        )
