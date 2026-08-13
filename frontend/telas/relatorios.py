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
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
)

from services.api import configuracoes
from services.venda_service import listar_vendas
from services.produto_service import listar_produtos
from services.caixa_service import historico_caixa

from design import tokens
from design.icons import icone
from design.widgets import BotaoSecundario, CardKPI, SecaoCard
from utils.formatacao import formatar_moeda


NOMES_FORMA_PAGAMENTO = {
    "DINHEIRO": "Dinheiro",
    "PIX": "PIX",
    "DEBITO": "Débito",
    "CREDITO": "Crédito",
    "BOLETO": "Boleto",
    "PRAZO": "A Prazo",
}

CORES_FORMA_PAGAMENTO = {
    "DINHEIRO": tokens.SECUNDARIA,
    "PIX": tokens.PRIMARIA,
    "DEBITO": tokens.ALERTA,
    "CREDITO": "#8E24AA",
    "BOLETO": tokens.TEXTO_SECUNDARIO,
    "PRAZO": tokens.ERRO,
}


class LinhaBarra(QFrame):
    """Uma linha de 'Nome / valor' com uma barra de progresso simples,
    usada tanto no ranking de produtos quanto no mix de pagamentos.
    Mantém a mesma assinatura de sempre porque telas/visao_geral.py
    também importa e usa esta classe diretamente."""

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
        lbl_titulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_BASE}px; font-weight:700; color:{tokens.TEXTO};
            background:transparent;
        """)

        col_texto.addWidget(lbl_titulo)

        if subtitulo:
            lbl_sub = QLabel(subtitulo)
            lbl_sub.setStyleSheet(f"""
                font-size:{tokens.TAMANHO_XS}px; color:{tokens.TEXTO_TERCIARIO};
                background:transparent;
            """)
            col_texto.addWidget(lbl_sub)

        topo.addLayout(col_texto)
        topo.addStretch()

        lbl_valor = QLabel(valor_texto)
        lbl_valor.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_BASE}px; font-weight:700; color:{cor};
            background:transparent;
        """)

        topo.addWidget(lbl_valor)

        layout.addLayout(topo)

        barra_fundo = QFrame()
        barra_fundo.setFixedHeight(6)
        barra_fundo.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:3px; border:none;
        """)

        barra_layout = QHBoxLayout(barra_fundo)
        barra_layout.setContentsMargins(0, 0, 0, 0)

        barra_preenchida = QFrame()
        barra_preenchida.setFixedHeight(6)
        barra_preenchida.setStyleSheet(
            f"background:{cor}; border-radius:3px; border:none;"
        )

        largura_relativa = max(0, min(100, round(percentual)))

        barra_layout.addWidget(barra_preenchida, largura_relativa)
        barra_layout.addStretch(max(1, 100 - largura_relativa))

        layout.addWidget(barra_fundo)


class PainelSecao(QFrame):
    """Card com cabeçalho (ícone emoji + título) e corpo substituível.
    Mantém a assinatura PainelSecao(icone, titulo) porque
    telas/visao_geral.py também importa e instancia esta classe
    diretamente com essa ordem de parâmetros."""

    def __init__(self, icone, titulo):

        super().__init__()

        self.setStyleSheet(f"""
            QFrame {{
                background:{tokens.CARD};
                border-radius:{tokens.RADIUS_LG}px;
                border:1px solid {tokens.BORDA};
            }}
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
        lbl_titulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_LG}px; font-weight:700; color:{tokens.TEXTO};
            background:transparent; border:none;
        """)

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
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"""
            color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_SM}px;
            background:transparent; border:none; padding:12px;
        """)
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

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(12)

        self.bt_voltar = QPushButton()
        self.bt_voltar.setFixedSize(36, 36)
        self.bt_voltar.setCursor(Qt.PointingHandCursor)
        self.bt_voltar.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
        self.bt_voltar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Relatórios")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel("GERENCIAMENTO E INTELIGÊNCIA")
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO}; font-weight:700;
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addSpacing(4)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()

        self.bt_imprimir = BotaoSecundario("Imprimir Relatório", icone_nome="printer")
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
        linha_abas.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
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

    @staticmethod
    def _pagina_rolavel(margens=(0, 12, 0, 0), espacamento=16):
        """Monta o esqueleto comum das 3 abas: um QWidget com
        QScrollArea ocupando 100% do espaco, pra nenhuma delas cortar
        conteudo quando a janela for menor que o conteudo. Devolve
        (pagina, conteudo_layout) -- o chamador so usa conteudo_layout
        pra tudo que ja adicionava direto em 'layout' antes."""

        pagina = QWidget()
        layout_pagina = QVBoxLayout(pagina)
        layout_pagina.setContentsMargins(0, 0, 0, 0)
        layout_pagina.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        conteudo = QWidget()
        conteudo.setStyleSheet("background:transparent;")

        conteudo_layout = QVBoxLayout(conteudo)
        conteudo_layout.setContentsMargins(*margens)
        conteudo_layout.setSpacing(espacamento)

        scroll.setWidget(conteudo)
        layout_pagina.addWidget(scroll)

        return pagina, conteudo_layout

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

        pagina, layout = self._pagina_rolavel()

        filtro_layout = QHBoxLayout()

        self.combo_periodo = QComboBox()
        self.combo_periodo.addItems(self.PERIODOS)
        self.combo_periodo.setCurrentText("Este mês")
        self.combo_periodo.setMinimumHeight(38)
        self.combo_periodo.setCursor(Qt.PointingHandCursor)
        self.combo_periodo.setStyleSheet(f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:4px 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """)
        self.combo_periodo.currentTextChanged.connect(
            self._atualizar_financeiro
        )

        filtro_layout.addWidget(self.combo_periodo)
        filtro_layout.addStretch()

        layout.addLayout(filtro_layout)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)

        self.card_faturamento = CardKPI("Faturamento Bruto", "dollar-sign", tokens.PRIMARIA)
        self.card_volume = CardKPI("Volume de Vendas", "shopping-cart", tokens.PRIMARIA)
        self.card_ticket = CardKPI("Ticket Médio", "trending-up", tokens.SECUNDARIA)

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

        self.card_faturamento.definir_valor(formatar_moeda(faturamento))
        self.card_volume.definir_valor(str(volume))
        self.card_ticket.definir_valor(formatar_moeda(ticket_medio))

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
                formatar_moeda(total),
                percentual,
                tokens.PRIMARIA,
            )

            self.painel_ranking.corpo.addWidget(linha)

    def _atualizar_mix_pagamentos(self, vendas_periodo):

        self.painel_mix.limpar_corpo()

        totais_por_forma = {}

        for venda in vendas_periodo:

            valor_total = float(venda.get("valor_total", 0))
            forma_2 = venda.get("forma_pagamento_2")
            valor_2 = float(venda.get("valor_forma_2") or 0)

            if forma_2 and valor_2:
                # venda dividida em 2 formas — cada parcela conta
                # separado, senao o mix fica atribuindo o valor
                # inteiro pra forma principal
                forma_1 = venda.get("forma_pagamento", "DINHEIRO")
                valor_1 = valor_total - valor_2

                totais_por_forma[forma_1] = (
                    totais_por_forma.get(forma_1, 0) + valor_1
                )
                totais_por_forma[forma_2] = (
                    totais_por_forma.get(forma_2, 0) + valor_2
                )
            else:
                forma = venda.get("forma_pagamento", "DINHEIRO")
                totais_por_forma[forma] = (
                    totais_por_forma.get(forma, 0) + valor_total
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
            cor = CORES_FORMA_PAGAMENTO.get(forma, tokens.TEXTO)

            linha = LinhaBarra(
                nome,
                f"{percentual:.1f}% do total",
                formatar_moeda(total),
                percentual,
                cor,
            )

            self.painel_mix.corpo.addWidget(linha)

    # ==========================================
    # PÁGINA: RELATÓRIO DE CAIXA
    # ==========================================

    def _criar_pagina_caixa(self):

        pagina, layout = self._pagina_rolavel(espacamento=12)

        titulo = QLabel("Histórico de Caixas")
        titulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_LG}px; font-weight:700; color:{tokens.TEXTO};
            background:transparent;
        """)
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

        self.tabela_caixa.setMinimumHeight(360)
        layout.addWidget(self.tabela_caixa)
        layout.addStretch()

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
                    formatar_moeda(caixa.get("saldo_inicial", 0))
                ),
            )
            self.tabela_caixa.setItem(
                linha, 2,
                QTableWidgetItem(
                    "—" if status == "ABERTO"
                    else formatar_moeda(saldo_final)
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

        pagina, layout = self._pagina_rolavel(espacamento=12)

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

        self.tabela_estoque.setMinimumHeight(360)
        layout.addWidget(self.tabela_estoque)
        layout.addStretch()

        return pagina

    def _botao_filtro_estoque(self, texto):

        botao = QPushButton(texto)
        botao.setCheckable(True)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setMinimumHeight(34)
        botao.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; color:{tokens.TEXTO_SECUNDARIO};
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_PILL}px;
                padding:0 16px; font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            }}
            QPushButton:checked {{
                background:{tokens.SIDEBAR}; color:white; border:1px solid {tokens.SIDEBAR};
            }}
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
            "NORMAL": tokens.SECUNDARIA_HOVER,
            "CRITICO": "#B45309",
            "ESGOTADO": tokens.ERRO,
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
                    formatar_moeda(produto.get("preco_venda", 0))
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

        tabela.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                alternate-background-color: {tokens.FUNDO};
                font-size: {tokens.TAMANHO_BASE}px;
            }}
            QTableWidget::item:selected {{
                background: {tokens.PRIMARIA};
                color: white;
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
