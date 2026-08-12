import csv
from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from services.cliente_service import listar_clientes
from services.financeiro_service import fluxo_caixa
from services.produto_service import listar_produtos
from services.relatorio_service import relatorio_vendas
from widgets.cards.card import Card
from widgets.charts.grafico_barras import GraficoBarras
from widgets.dialogs.message_dialog import Mensagem
from widgets.tables.standard_table import StandardTable

# Limite generoso o bastante pra loja de bairro/pequeno porte não precisar
# de paginação de verdade na tabela — traz tudo de uma vez e filtra/ordena
# do lado do cliente, evitando construir uma UI de página anterior/próxima
# pra um volume de dados que cabe inteiro na tela sem problema.
LIMITE_TABELA = 500

FORMAS_PAGAMENTO_LABEL = {
    "DINHEIRO": "Dinheiro",
    "PIX": "PIX",
    "DEBITO": "Cartão de Débito",
    "CREDITO": "Cartão de Crédito",
    "BOLETO": "Boleto",
    "PRAZO": "Prazo (Fiado)",
}

PERIODOS_VENDAS = [
    "Hoje",
    "Ontem",
    "7 dias",
    "30 dias",
    "Este mês",
    "Mês passado",
    "Personalizado",
]

PERIODOS_FLUXO_CAIXA = [
    "Próximos 7 dias",
    "Próximos 15 dias",
    "Próximos 30 dias",
    "Próximos 60 dias",
    "Próximos 90 dias",
]

# categoria -> [(chave, rótulo, disponível)]
MENU_RELATORIOS = [
    ("VENDAS", [
        ("vendas_geral", "Relatório Geral", True),
        ("vendas_cliente", "Vendas por Cliente", False),
        ("vendas_produto", "Vendas por Produto", False),
        ("vendas_categoria", "Vendas por Categoria", False),
        ("cancelamentos", "Cancelamentos", False),
    ]),
    ("FINANCEIRO", [
        ("fluxo_caixa", "Fluxo de Caixa", True),
        ("contas_receber", "Contas a Receber", False),
        ("contas_pagar", "Contas a Pagar", False),
        ("lucro", "Lucro", False),
    ]),
    ("ESTOQUE", [
        ("estoque_atual", "Estoque Atual", False),
        ("movimentacoes", "Movimentações", False),
    ]),
    ("CLIENTES", [
        ("clientes_cadastrados", "Clientes Cadastrados", False),
        ("clientes_inadimplentes", "Clientes Inadimplentes", False),
    ]),
    ("FORNECEDORES", [
        ("compras_fornecedor", "Compras", False),
    ]),
]


class Relatorios(QWidget):

    def __init__(self):
        super().__init__()

        self.relatorio_atual = "vendas_geral"
        self.dados_atuais = None

        self.setStyleSheet("""
            QWidget { background: #F4F6F9; }
            QFrame#painel {
                background: white;
                border: 1px solid #E0E3E9;
                border-radius: 12px;
            }
            QComboBox, QLineEdit {
                padding: 6px 8px;
                border: 1px solid #dcdcdc;
                border-radius: 6px;
                background: white;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        layout.addWidget(self._montar_topo())

        corpo = QHBoxLayout()
        corpo.setSpacing(16)

        corpo.addWidget(self._montar_menu(), 0)

        self.area_direita = QVBoxLayout()
        self.area_direita.setSpacing(16)

        self.area_direita.addWidget(self._montar_filtros())
        self.area_direita.addLayout(self._montar_cards())
        self.area_direita.addWidget(self._montar_graficos())
        self.area_direita.addWidget(self._montar_tabela())

        corpo.addLayout(self.area_direita, 1)

        layout.addLayout(corpo)

        self._atualizar_visibilidade_por_relatorio()
        self.atualizar()

    # ==================================================
    # TOPO
    # ==================================================

    def _montar_topo(self):
        frame = QFrame()

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        titulos = QVBoxLayout()

        titulo = QLabel("RELATÓRIOS")
        titulo.setStyleSheet("font-size:26px; font-weight:bold;")

        subtitulo = QLabel(
            "Visualize indicadores, exporte documentos e acompanhe o "
            "desempenho da loja."
        )
        subtitulo.setStyleSheet("font-size:13px; color:#757575;")

        titulos.addWidget(titulo)
        titulos.addWidget(subtitulo)

        layout.addLayout(titulos)
        layout.addStretch()

        botoes = [
            ("Atualizar", "#616161", "#424242", self.atualizar),
            ("Exportar PDF", "#1565C0", "#0D47A1", self.exportar_pdf),
            ("Exportar CSV", "#1565C0", "#0D47A1", self.exportar_csv),
            ("Imprimir", "#2E7D32", "#1B5E20", self.imprimir),
        ]

        for texto, cor, cor_hover, acao in botoes:
            botao = QPushButton(texto)
            botao.setStyleSheet(f"""
                QPushButton {{
                    background:{cor};
                    color:white;
                    font-weight:bold;
                    border:none;
                    border-radius:6px;
                    padding:8px 16px;
                }}
                QPushButton:hover {{
                    background:{cor_hover};
                }}
            """)
            botao.clicked.connect(acao)
            layout.addWidget(botao)

        return frame

    # ==================================================
    # MENU LATERAL (CATEGORIAS DE RELATÓRIO)
    # ==================================================

    def _montar_menu(self):
        frame = QFrame()
        frame.setObjectName("painel")
        frame.setFixedWidth(220)

        layout = QVBoxLayout(frame)
        layout.setSpacing(4)

        self.botoes_relatorio = {}

        for categoria, itens in MENU_RELATORIOS:
            titulo_categoria = QLabel(categoria)
            titulo_categoria.setStyleSheet(
                "font-size:11px; font-weight:bold; color:#9AA0A6; "
                "padding-top:10px;"
            )
            layout.addWidget(titulo_categoria)

            for chave, rotulo, disponivel in itens:
                botao = QPushButton(
                    rotulo if disponivel else f"{rotulo} (em breve)"
                )
                botao.setEnabled(disponivel)
                botao.setCheckable(True)
                botao.setStyleSheet("""
                    QPushButton {
                        text-align:left;
                        border:none;
                        border-radius:6px;
                        padding:8px 10px;
                        color:#333;
                    }
                    QPushButton:hover:enabled {
                        background:#EEF3FB;
                    }
                    QPushButton:checked {
                        background:#1565C0;
                        color:white;
                        font-weight:bold;
                    }
                    QPushButton:disabled {
                        color:#BBB;
                    }
                """)

                if disponivel:
                    botao.clicked.connect(
                        lambda _, c=chave: self.selecionar_relatorio(c)
                    )

                layout.addWidget(botao)

                self.botoes_relatorio[chave] = botao

        self.botoes_relatorio[self.relatorio_atual].setChecked(True)

        layout.addStretch()

        return frame

    def selecionar_relatorio(self, chave):

        if chave == self.relatorio_atual:
            return

        self.botoes_relatorio[self.relatorio_atual].setChecked(False)
        self.relatorio_atual = chave
        self.botoes_relatorio[chave].setChecked(True)

        self._atualizar_visibilidade_por_relatorio()
        self.atualizar()

    # ==================================================
    # FILTROS
    # ==================================================

    def _montar_filtros(self):
        self.frame_filtros = QFrame()
        self.frame_filtros.setObjectName("painel")

        layout = QHBoxLayout(self.frame_filtros)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Período"))

        self.combo_periodo = QComboBox()
        self.combo_periodo.setMinimumWidth(160)
        layout.addWidget(self.combo_periodo)

        self.lbl_cliente = QLabel("Cliente")
        self.combo_cliente = QComboBox()
        self.combo_cliente.addItem("Todos", None)
        for cliente in listar_clientes():
            self.combo_cliente.addItem(cliente["nome"], cliente["id"])

        self.lbl_produto = QLabel("Produto")
        self.combo_produto = QComboBox()
        self.combo_produto.addItem("Todos", None)

        self.produtos_cache = listar_produtos()

        for produto in self.produtos_cache:
            self.combo_produto.addItem(produto["nome"], produto["id"])

        self.lbl_categoria = QLabel("Categoria")
        self.combo_categoria = QComboBox()
        self.combo_categoria.addItem("Todas", None)

        categorias = sorted({
            produto["categoria"]
            for produto in self.produtos_cache
            if produto.get("categoria")
        })
        for categoria in categorias:
            self.combo_categoria.addItem(categoria, categoria)

        self.lbl_forma = QLabel("Forma de Pagamento")
        self.combo_forma = QComboBox()
        self.combo_forma.addItem("Todas", None)
        for forma, rotulo in FORMAS_PAGAMENTO_LABEL.items():
            self.combo_forma.addItem(rotulo, forma)

        self.lbl_status = QLabel("Status")
        self.combo_status = QComboBox()
        self.combo_status.addItem("Finalizadas", "FINALIZADA")
        self.combo_status.addItem("Canceladas", "CANCELADA")

        for widget in (
            self.lbl_cliente, self.combo_cliente,
            self.lbl_produto, self.combo_produto,
            self.lbl_categoria, self.combo_categoria,
            self.lbl_forma, self.combo_forma,
            self.lbl_status, self.combo_status,
        ):
            layout.addWidget(widget)

        layout.addStretch()

        bt_aplicar = QPushButton("Aplicar")
        bt_aplicar.setStyleSheet("""
            QPushButton {
                background:#1565C0; color:white; font-weight:bold;
                border:none; border-radius:6px; padding:8px 16px;
            }
            QPushButton:hover { background:#0D47A1; }
        """)
        bt_aplicar.clicked.connect(self.atualizar)

        bt_limpar = QPushButton("Limpar")
        bt_limpar.setStyleSheet("""
            QPushButton {
                background:#E0E0E0; font-weight:bold;
                border:none; border-radius:6px; padding:8px 16px;
            }
            QPushButton:hover { background:#CFCFCF; }
        """)
        bt_limpar.clicked.connect(self.limpar_filtros)

        layout.addWidget(bt_limpar)
        layout.addWidget(bt_aplicar)

        return self.frame_filtros

    def _atualizar_visibilidade_por_relatorio(self):

        eh_vendas = self.relatorio_atual == "vendas_geral"

        self.combo_periodo.blockSignals(True)
        self.combo_periodo.clear()
        self.combo_periodo.addItems(
            PERIODOS_VENDAS if eh_vendas else PERIODOS_FLUXO_CAIXA
        )
        self.combo_periodo.blockSignals(False)

        for widget in (
            self.lbl_cliente, self.combo_cliente,
            self.lbl_produto, self.combo_produto,
            self.lbl_categoria, self.combo_categoria,
            self.lbl_forma, self.combo_forma,
            self.lbl_status, self.combo_status,
        ):
            widget.setVisible(eh_vendas)

        self.grid_cards_vendas_widget.setVisible(eh_vendas)
        self.grid_cards_fluxo_widget.setVisible(not eh_vendas)
        self.frame_graficos.setVisible(eh_vendas)

    def limpar_filtros(self):
        self.combo_periodo.setCurrentIndex(0)
        self.combo_cliente.setCurrentIndex(0)
        self.combo_produto.setCurrentIndex(0)
        self.combo_categoria.setCurrentIndex(0)
        self.combo_forma.setCurrentIndex(0)
        self.combo_status.setCurrentIndex(0)
        self.atualizar()

    def _calcular_periodo(self):
        hoje = date.today()
        opcao = self.combo_periodo.currentText()

        if opcao == "Hoje":
            return hoje, hoje

        if opcao == "Ontem":
            ontem = hoje - timedelta(days=1)
            return ontem, ontem

        if opcao == "7 dias":
            return hoje - timedelta(days=6), hoje

        if opcao == "30 dias":
            return hoje - timedelta(days=29), hoje

        if opcao == "Este mês":
            return hoje.replace(day=1), hoje

        if opcao == "Mês passado":
            primeiro_dia_atual = hoje.replace(day=1)
            ultimo_dia_passado = primeiro_dia_atual - timedelta(days=1)
            return ultimo_dia_passado.replace(day=1), ultimo_dia_passado

        # "Personalizado" cai aqui também, por enquanto tratado como hoje
        # (sem seletor de data customizada ainda).
        return hoje, hoje

    # ==================================================
    # CARDS
    # ==================================================

    def _montar_cards(self):
        layout = QVBoxLayout()

        self.grid_cards_vendas_widget = QWidget()
        self.grid_cards_vendas = QGridLayout(self.grid_cards_vendas_widget)
        self.grid_cards_vendas.setSpacing(16)

        self.grid_cards_fluxo_widget = QWidget()
        self.grid_cards_fluxo = QGridLayout(self.grid_cards_fluxo_widget)
        self.grid_cards_fluxo.setSpacing(16)

        layout.addWidget(self.grid_cards_vendas_widget)
        layout.addWidget(self.grid_cards_fluxo_widget)

        return layout

    def _limpar_grid(self, grid):
        while grid.count():
            item = grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _moeda(self, valor):
        return f"R$ {valor:.2f}"

    # ==================================================
    # GRÁFICOS
    # ==================================================

    def _montar_graficos(self):
        self.frame_graficos = QFrame()
        layout = QHBoxLayout(self.frame_graficos)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self.container_graficos = layout

        return self.frame_graficos

    def _limpar_graficos(self):
        while self.container_graficos.count():
            item = self.container_graficos.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    # ==================================================
    # TABELA
    # ==================================================

    def _montar_tabela(self):
        frame = QFrame()
        frame.setObjectName("painel")

        layout = QVBoxLayout(frame)

        cabecalho = QHBoxLayout()

        self.lbl_resultado = QLabel("")
        self.lbl_resultado.setStyleSheet("color:#757575; font-size:12px;")
        cabecalho.addWidget(self.lbl_resultado)

        cabecalho.addStretch()

        self.busca_tabela = QLineEdit()
        self.busca_tabela.setPlaceholderText("Pesquisar na tabela...")
        self.busca_tabela.setFixedWidth(240)
        self.busca_tabela.textChanged.connect(self._filtrar_tabela)
        cabecalho.addWidget(self.busca_tabela)

        layout.addLayout(cabecalho)

        self.colunas_vendas = [
            "Data", "Cliente", "Valor", "Forma de Pagamento", "Status"
        ]
        self.colunas_fluxo = ["Vencimento", "Tipo", "Descrição", "Valor"]

        self.tabela = StandardTable(self.colunas_vendas)
        self.tabela.setSortingEnabled(True)
        layout.addWidget(self.tabela)

        self._linhas_tabela_completa = []

        return frame

    def _filtrar_tabela(self):
        texto = self.busca_tabela.text().strip().lower()

        if not texto:
            linhas = self._linhas_tabela_completa
        else:
            linhas = [
                linha
                for linha in self._linhas_tabela_completa
                if texto in " ".join(
                    str(valor).lower() for valor in linha.values()
                )
            ]

        campos = (
            ["data", "cliente", "valor", "forma_pagamento", "status"]
            if self.relatorio_atual == "vendas_geral"
            else ["vencimento", "tipo", "descricao", "valor"]
        )

        self.tabela.preencher(linhas, campos)

    # ==================================================
    # CARREGAR / ATUALIZAR
    # ==================================================

    def atualizar(self):

        if self.relatorio_atual == "vendas_geral":
            self._carregar_vendas_geral()
        elif self.relatorio_atual == "fluxo_caixa":
            self._carregar_fluxo_caixa()

    def _carregar_vendas_geral(self):

        data_inicio, data_fim = self._calcular_periodo()

        try:
            dados = relatorio_vendas(
                data_inicio.isoformat(),
                data_fim.isoformat(),
                limit=LIMITE_TABELA,
                cliente_id=self.combo_cliente.currentData(),
                produto_id=self.combo_produto.currentData(),
                categoria=self.combo_categoria.currentData(),
                forma_pagamento=self.combo_forma.currentData(),
                status=self.combo_status.currentData(),
            )
        except Exception as e:
            Mensagem.erro(self, str(e))
            return

        self.dados_atuais = dados

        self._limpar_grid(self.grid_cards_vendas)

        def _card(titulo, chave, cor, coluna_grid, formatar=self._moeda):
            kpi = dados[chave]
            card = Card(
                titulo,
                formatar(kpi["atual"]),
                cor=cor,
                variacao=kpi["variacao_pct"],
            )
            linha, coluna = divmod(coluna_grid, 4)
            self.grid_cards_vendas.addWidget(card, linha, coluna)

        _card("💰 Receita Total", "receita_total", "#2E7D32", 0)
        _card("📈 Lucro", "lucro", "#1565C0", 1)
        _card(
            "🧾 Qtde de Vendas", "quantidade_vendas", "#6A1B9A", 2,
            formatar=lambda v: str(int(v)),
        )
        _card("🎯 Ticket Médio", "ticket_medio", "#EF6C00", 3)
        _card(
            "👥 Clientes Atendidos", "clientes_atendidos", "#3949AB", 4,
            formatar=lambda v: str(int(v)),
        )
        _card(
            "📦 Produtos Vendidos", "produtos_vendidos", "#8D6E63", 5,
            formatar=lambda v: str(int(v)),
        )
        _card(
            "📊 Margem de Lucro", "margem_lucro", "#C62828", 6,
            formatar=lambda v: f"{v:.1f}%",
        )

        self._limpar_graficos()

        self.container_graficos.addWidget(
            GraficoBarras(
                "Vendas por Dia", dados["vendas_por_dia"], "data", "total",
                cor="#1565C0",
            )
        )
        self.container_graficos.addWidget(
            GraficoBarras(
                "Produtos Mais Vendidos", dados["top_produtos"],
                "produto", "quantidade", cor="#2E7D32",
                formato_valor="@value un.", formato_eixo_y="%.0f",
            )
        )
        self.container_graficos.addWidget(
            GraficoBarras(
                "Formas de Pagamento",
                [
                    {**item, "forma_pagamento": FORMAS_PAGAMENTO_LABEL.get(
                        item["forma_pagamento"], item["forma_pagamento"]
                    )}
                    for item in dados["formas_pagamento"]
                ],
                "forma_pagamento", "total", cor="#EF6C00",
            )
        )

        self.lbl_resultado.setText(
            f"Mostrando {len(dados['vendas'])} de {dados['vendas_total']} "
            "vendas no período"
        )

        self.tabela.setColumnCount(len(self.colunas_vendas))
        self.tabela.setHorizontalHeaderLabels(self.colunas_vendas)

        self._linhas_tabela_completa = [
            {
                "data": venda["data"][:10],
                "cliente": venda["cliente"] or "-",
                "valor": self._moeda(venda["valor_total"]),
                "forma_pagamento": FORMAS_PAGAMENTO_LABEL.get(
                    venda["forma_pagamento"], venda["forma_pagamento"]
                ),
                "status": venda["status"],
            }
            for venda in dados["vendas"]
        ]

        self.busca_tabela.clear()
        self._filtrar_tabela()

    def _carregar_fluxo_caixa(self):

        rotulo_dias = self.combo_periodo.currentText()
        dias = int("".join(filter(str.isdigit, rotulo_dias)) or 30)

        dados = fluxo_caixa(dias)

        if dados is None:
            Mensagem.erro(self, "Não foi possível carregar o fluxo de caixa.")
            return

        self.dados_atuais = dados

        self._limpar_grid(self.grid_cards_fluxo)

        cards = [
            ("Saldo Atual", dados["saldo_atual"], "#1565C0"),
            ("A Receber", dados["total_a_receber"], "#2E7D32"),
            ("A Pagar", dados["total_a_pagar"], "#C62828"),
            ("Saldo Projetado", dados["saldo_projetado"], "#6A1B9A"),
        ]

        for coluna, (titulo, valor, cor) in enumerate(cards):
            card = Card(titulo, self._moeda(valor), cor=cor)
            self.grid_cards_fluxo.addWidget(card, 0, coluna)

        self.lbl_resultado.setText(
            f"{len(dados['itens'])} lançamento(s) nos próximos {dias} dias"
        )

        self.tabela.setColumnCount(len(self.colunas_fluxo))
        self.tabela.setHorizontalHeaderLabels(self.colunas_fluxo)

        self._linhas_tabela_completa = [
            {
                "vencimento": item["data_vencimento"][:10],
                "tipo": (
                    "A Receber" if item["tipo"] == "A_RECEBER"
                    else "A Pagar"
                ),
                "descricao": item["descricao"] or "-",
                "valor": self._moeda(item["valor"]),
            }
            for item in dados["itens"]
        ]

        self.busca_tabela.clear()
        self._filtrar_tabela()

    # ==================================================
    # EXPORTAÇÃO / IMPRESSÃO
    # ==================================================

    def _montar_html_relatorio(self):

        if not self.dados_atuais:
            return None

        titulo = (
            "Relatório Geral de Vendas"
            if self.relatorio_atual == "vendas_geral"
            else "Fluxo de Caixa"
        )

        linhas_html = "".join(
            "<tr>" + "".join(f"<td>{valor}</td>" for valor in linha.values())
            + "</tr>"
            for linha in self._linhas_tabela_completa
        )

        colunas = (
            self.colunas_vendas
            if self.relatorio_atual == "vendas_geral"
            else self.colunas_fluxo
        )

        cabecalho_colunas = "".join(f"<th>{coluna}</th>" for coluna in colunas)

        return f"""
        <h2 style='text-align:center;'>{titulo}</h2>
        <p style='text-align:center;'>Vertex ERP</p>
        <table width='100%' cellspacing='0' cellpadding='4' border='1'>
            <tr>{cabecalho_colunas}</tr>
            {linhas_html}
        </table>
        """

    def exportar_pdf(self):

        html = self._montar_html_relatorio()

        if html is None:
            Mensagem.aviso(self, "Nenhum relatório carregado.")
            return

        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar PDF", "", "PDF (*.pdf)"
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".pdf"):
            caminho += ".pdf"

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(caminho)

        documento = QTextDocument()
        documento.setHtml(html)
        documento.print_(printer)

        Mensagem.sucesso(self, f"PDF exportado em:\n{caminho}")

    def exportar_csv(self):

        if not self._linhas_tabela_completa:
            Mensagem.aviso(self, "Nenhum dado pra exportar.")
            return

        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar CSV", "", "CSV (*.csv)"
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".csv"):
            caminho += ".csv"

        colunas = (
            self.colunas_vendas
            if self.relatorio_atual == "vendas_geral"
            else self.colunas_fluxo
        )

        with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:
            escritor = csv.writer(arquivo, delimiter=";")
            escritor.writerow(colunas)

            for linha in self._linhas_tabela_completa:
                escritor.writerow(linha.values())

        Mensagem.sucesso(self, f"CSV exportado em:\n{caminho}")

    def imprimir(self):

        html = self._montar_html_relatorio()

        if html is None:
            Mensagem.aviso(self, "Nenhum relatório carregado.")
            return

        impressora_padrao = QPrinterInfo.defaultPrinter()

        if impressora_padrao.isNull():
            Mensagem.aviso(
                self,
                "Nenhuma impressora padrão configurada no Windows."
            )
            return

        printer = QPrinter(impressora_padrao, QPrinter.HighResolution)

        documento = QTextDocument()
        documento.setHtml(html)
        documento.print_(printer)
