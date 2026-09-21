from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTimer, Signal
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
from services.relatorio_service import (
    relatorio_vendas,
    curva_abc,
    comparativo_lojas,
    comparativo_estoque,
    sugestao_reposicao,
)
from services.produto_service import listar_produtos
from services.caixa_service import historico_caixa
from services.loja_service import listar_lojas
from services.worker import rodar_em_thread, em_paralelo


def _listar_lojas_para_combo(combo):
    """Roda na worker thread -- `combo` so' viaja de ida e volta junto
    com o resultado (nao chamado/tocado aqui, so' repassado; ver
    services/worker.py sobre por que o callback nao pode ser uma
    lambda que "lembra" o combo via closure)."""
    return listar_lojas(), combo


def _buscar_dados_relatorio_geral(loja_id_caixa):
    """Roda na worker thread -- as 2 chamadas que carregar() precisa
    (a 3a, relatorio_vendas, fica em _atualizar_financeiro, que ja e'
    independente/refeita sozinha quando o filtro financeiro muda).
    As 2 sao independentes, entao disparam em paralelo."""
    return em_paralelo((listar_produtos,), (historico_caixa, loja_id_caixa))

from design import tokens
from design.charts import GraficoArea
from design.icons import icone
from design.widgets import BotaoSecundario, CardKPI, SecaoCard
from utils.formatacao import formatar_moeda
from widgets.dialogs.message_dialog import Mensagem


NOMES_FORMA_PAGAMENTO = {
    "DINHEIRO": "Dinheiro",
    "PIX": "PIX",
    "DEBITO": "Débito",
    "CREDITO": "Crédito",
    "BOLETO": "Boleto",
    "PRAZO": "Crediário",
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

        self.produtos = []
        self.caixas = []
        self._carregando = False
        self._carregando_financeiro = False
        self._carregando_caixa = False

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
        self.bt_voltar.setToolTip("Voltar")
        self.bt_voltar.setAccessibleName("Voltar")
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

        subtitulo = QLabel("Gerenciamento e inteligência")
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
        # debounced: cada mudanca de periodo dispara uma chamada de
        # rede pro backend (agregado agora, nao mais um filtro local)
        # -- sem isso, alguem clicando rapido por varias opcoes do
        # combo dispararia uma requisicao sincrona bloqueante por
        # clique. Reiniciar o timer a cada mudanca faz so a ultima
        # selecao "vencer".
        self._timer_atualizar_financeiro = QTimer(self)
        self._timer_atualizar_financeiro.setSingleShot(True)
        self._timer_atualizar_financeiro.timeout.connect(
            self._atualizar_financeiro
        )
        self.combo_periodo.currentTextChanged.connect(
            lambda: self._timer_atualizar_financeiro.start(300)
        )

        self.combo_loja = QComboBox()
        self.combo_loja.setMinimumHeight(38)
        self.combo_loja.setCursor(Qt.PointingHandCursor)
        self.combo_loja.setStyleSheet(f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:4px 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """)
        self._carregar_combo_lojas(self.combo_loja)
        self.combo_loja.currentIndexChanged.connect(
            lambda: self._timer_atualizar_financeiro.start(300)
        )

        filtro_layout.addWidget(self.combo_periodo)
        filtro_layout.addWidget(self.combo_loja)
        filtro_layout.addStretch()

        layout.addLayout(filtro_layout)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(14)

        self.card_faturamento = CardKPI(
            "Faturamento Bruto", "dollar-sign", tokens.PRIMARIA, destaque=True
        )
        self.card_volume = CardKPI("Volume de Vendas", "shopping-cart", tokens.PRIMARIA)
        self.card_ticket = CardKPI("Ticket Médio", "trending-up", tokens.SECUNDARIA)

        cards_layout.addWidget(self.card_faturamento)
        cards_layout.addWidget(self.card_volume)
        cards_layout.addWidget(self.card_ticket)

        layout.addLayout(cards_layout)

        painel_tendencia = PainelSecao("📈", "Faturamento no Período")
        self.grafico_tendencia = GraficoArea()
        painel_tendencia.corpo.addWidget(self.grafico_tendencia)
        layout.addWidget(painel_tendencia)

        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(16)

        self.painel_ranking = PainelSecao("📦", "Ranking de Produtos")
        self.painel_mix = PainelSecao("💳", "Mix de Pagamentos")

        grid_layout.addWidget(self.painel_ranking, stretch=1)
        grid_layout.addWidget(self.painel_mix, stretch=1)

        layout.addLayout(grid_layout)

        self.painel_comparativo_lojas = PainelSecao("🏬", "Comparativo entre Lojas")

        self.tabela_comparativo_lojas = QTableWidget()
        self.tabela_comparativo_lojas.setColumnCount(5)
        self.tabela_comparativo_lojas.setHorizontalHeaderLabels(
            ["Loja", "Faturamento", "Lucro", "Qtd. Vendas", "Ticket Médio"]
        )
        self._estilizar_tabela(self.tabela_comparativo_lojas)
        self.tabela_comparativo_lojas.setMinimumHeight(150)
        self.painel_comparativo_lojas.corpo.addWidget(self.tabela_comparativo_lojas)

        layout.addWidget(self.painel_comparativo_lojas)
        layout.addStretch()

        return pagina

    def _periodo_selecionado(self):
        """Traduz a opção escolhida no combo pra um intervalo (inicio,
        fim) de datas -- mesmos limites de sempre, só que agora servem
        pra montar a query do relatório agregado no backend em vez de
        filtrar uma lista de vendas já em memória."""

        return self._calcular_periodo(self.combo_periodo)

    def _calcular_periodo(self, combo):
        """Mesma logica de _periodo_selecionado, parametrizada pelo
        combo -- usado tambem pelo combo de periodo da Curva ABC, que
        e' independente do combo do Centro Financeiro."""

        periodo = combo.currentText()
        hoje = datetime.now().date()

        if periodo == "Hoje":
            return hoje, hoje

        if periodo == "Ontem":
            ontem = hoje - timedelta(days=1)
            return ontem, ontem

        if periodo == "Últimos 7 dias":
            return hoje - timedelta(days=6), hoje

        if periodo == "Este mês":
            return hoje.replace(day=1), hoje

        if periodo == "Mês anterior":
            primeiro_dia_mes_atual = hoje.replace(day=1)
            fim = primeiro_dia_mes_atual - timedelta(days=1)
            return fim.replace(day=1), fim

        # "Tudo" -- inicio=None diz pro backend pra não aplicar limite
        # inferior nenhum, em vez de fingir isso com uma data hardcoded
        # (que descartaria vendas reais anteriores a ela e ainda
        # forçaria um cálculo de "período anterior" sem sentido pra
        # comparação -- ver RelatorioService.vendas_geral).
        return None, hoje

    def _carregar_combo_lojas(self, combo):

        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Todas as lojas", None)
        combo.blockSignals(False)

        rodar_em_thread(
            self,
            _listar_lojas_para_combo,
            combo,
            ao_sucesso=self._ao_carregar_combo_lojas_sucesso,
        )

    def _ao_carregar_combo_lojas_sucesso(self, resultado):

        lojas, combo = resultado

        combo.blockSignals(True)

        for loja in lojas:
            combo.addItem(loja["nome"], loja["id"])

        combo.blockSignals(False)

    def _atualizar_financeiro(self):

        if self._carregando_financeiro:
            return
        self._carregando_financeiro = True

        inicio, fim = self._periodo_selecionado()

        rodar_em_thread(
            self,
            relatorio_vendas,
            inicio.isoformat() if inicio else None,
            fim.isoformat(),
            limit=1,
            top_produtos_limite=10,
            top_produtos_ordenar_por="valor",
            loja_id=self.combo_loja.currentData(),
            ao_sucesso=self._ao_atualizar_financeiro_sucesso,
            ao_erro=self._ao_atualizar_financeiro_erro,
            ao_finalizar=self._ao_atualizar_financeiro_finalizado,
        )

        # comparativo entre lojas sempre mostra todas as lojas
        # (independe do filtro self.combo_loja) -- chamada paralela,
        # nao depende do resultado de relatorio_vendas acima
        rodar_em_thread(
            self,
            comparativo_lojas,
            inicio.isoformat() if inicio else None,
            fim.isoformat(),
            ao_sucesso=self._ao_atualizar_comparativo_lojas_sucesso,
            ao_erro=self._ao_atualizar_secao_secundaria_erro,
        )

    def _ao_atualizar_comparativo_lojas_sucesso(self, itens):

        self.tabela_comparativo_lojas.setRowCount(len(itens))

        for linha, item in enumerate(itens):
            self.tabela_comparativo_lojas.setItem(
                linha, 0, QTableWidgetItem(item["loja_nome"])
            )
            self.tabela_comparativo_lojas.setItem(
                linha, 1, QTableWidgetItem(formatar_moeda(item["receita_total"]))
            )
            self.tabela_comparativo_lojas.setItem(
                linha, 2, QTableWidgetItem(formatar_moeda(item["lucro"]))
            )
            self.tabela_comparativo_lojas.setItem(
                linha, 3, QTableWidgetItem(str(item["quantidade_vendas"]))
            )
            self.tabela_comparativo_lojas.setItem(
                linha, 4, QTableWidgetItem(formatar_moeda(item["ticket_medio"]))
            )

    def _ao_atualizar_financeiro_erro(self, erro):
        Mensagem.erro(
            self,
            "Não foi possível carregar o relatório financeiro.\n"
            f"Os valores exibidos abaixo não refletem o período "
            f"selecionado.\n\nDetalhes: {erro}",
        )
        self.card_faturamento.definir_valor(formatar_moeda(0))
        self.card_volume.definir_valor("0")
        self.card_ticket.definir_valor(formatar_moeda(0))
        self._atualizar_ranking_produtos([])
        self._atualizar_mix_pagamentos([])
        self.grafico_tendencia.definir_dados([], [])

    def _ao_atualizar_financeiro_finalizado(self):
        self._carregando_financeiro = False

    def _ao_atualizar_financeiro_sucesso(self, relatorio):

        faturamento = float(relatorio["receita_total"]["atual"])
        volume = int(relatorio["quantidade_vendas"]["atual"])
        ticket_medio = float(relatorio["ticket_medio"]["atual"])

        self.card_faturamento.definir_valor(formatar_moeda(faturamento))
        self.card_volume.definir_valor(str(volume))
        self.card_ticket.definir_valor(formatar_moeda(ticket_medio))

        self._atualizar_ranking_produtos(relatorio["top_produtos"])
        self._atualizar_mix_pagamentos(relatorio["formas_pagamento"])
        self._atualizar_tendencia(relatorio["vendas_por_dia"])

    def _atualizar_tendencia(self, vendas_por_dia):

        if not vendas_por_dia:
            self.grafico_tendencia.definir_dados([], [])
            return

        rotulos = []
        rotulos_completos = []
        valores = []

        for item in vendas_por_dia:
            dia = datetime.strptime(item["data"], "%Y-%m-%d")
            rotulos.append(dia.strftime("%d/%m"))
            rotulos_completos.append(dia.strftime("%d/%m/%Y"))
            valores.append(item["total"])

        self.grafico_tendencia.definir_dados(rotulos, valores, rotulos_completos)

    def _atualizar_ranking_produtos(self, top_produtos):

        self.painel_ranking.limpar_corpo()

        if not top_produtos:
            self.painel_ranking.adicionar_vazio(
                "Nenhuma venda no período selecionado."
            )
            return

        maior_valor = float(top_produtos[0]["total"]) or 1

        for posicao, item in enumerate(top_produtos, start=1):

            total = float(item["total"])

            percentual = (
                (total / maior_valor) * 100 if maior_valor else 0
            )

            linha = LinhaBarra(
                f"{posicao}. {item['produto']}",
                None,
                formatar_moeda(total),
                percentual,
                tokens.PRIMARIA,
            )

            self.painel_ranking.corpo.addWidget(linha)

    def _atualizar_mix_pagamentos(self, formas_pagamento):

        self.painel_mix.limpar_corpo()

        total_geral = sum(float(item["total"]) for item in formas_pagamento)

        if not total_geral:
            self.painel_mix.adicionar_vazio(
                "Nenhuma venda no período selecionado."
            )
            return

        # o backend (RelatorioService._formas_pagamento) já devolve a
        # lista ordenada do maior pro menor total
        for item in formas_pagamento:

            forma = item["forma_pagamento"]
            total = float(item["total"])
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

        cabecalho_caixa = QHBoxLayout()

        titulo = QLabel("Histórico de Caixas")
        titulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_LG}px; font-weight:700; color:{tokens.TEXTO};
            background:transparent;
        """)
        cabecalho_caixa.addWidget(titulo)
        cabecalho_caixa.addStretch()

        self.combo_loja_caixa = QComboBox()
        self.combo_loja_caixa.setMinimumHeight(34)
        self.combo_loja_caixa.setCursor(Qt.PointingHandCursor)
        self.combo_loja_caixa.setStyleSheet(f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:0 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """)
        self._carregar_combo_lojas(self.combo_loja_caixa)
        self.combo_loja_caixa.currentIndexChanged.connect(
            self._recarregar_historico_caixa
        )
        cabecalho_caixa.addWidget(self.combo_loja_caixa)

        layout.addLayout(cabecalho_caixa)

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

        # ==========================================
        # CURVA ABC
        # ==========================================
        painel_abc = PainelSecao("📈", "Curva ABC de Produtos")

        filtro_abc = QHBoxLayout()
        filtro_abc.setSpacing(8)

        self.combo_periodo_abc = QComboBox()
        self.combo_periodo_abc.addItems(self.PERIODOS)
        self.combo_periodo_abc.setCurrentText("Este mês")
        self.combo_periodo_abc.setMinimumHeight(36)
        self.combo_periodo_abc.setCursor(Qt.PointingHandCursor)
        self.combo_periodo_abc.setStyleSheet(f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:4px 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """)

        self.combo_loja_abc = QComboBox()
        self.combo_loja_abc.setMinimumHeight(36)
        self.combo_loja_abc.setCursor(Qt.PointingHandCursor)
        self.combo_loja_abc.setStyleSheet(self.combo_periodo_abc.styleSheet())
        self._carregar_combo_lojas(self.combo_loja_abc)

        self._timer_atualizar_abc = QTimer(self)
        self._timer_atualizar_abc.setSingleShot(True)
        self._timer_atualizar_abc.timeout.connect(self._atualizar_curva_abc)
        self.combo_periodo_abc.currentTextChanged.connect(
            lambda: self._timer_atualizar_abc.start(300)
        )
        self.combo_loja_abc.currentIndexChanged.connect(
            lambda: self._timer_atualizar_abc.start(300)
        )

        filtro_abc.addWidget(self.combo_periodo_abc)
        filtro_abc.addWidget(self.combo_loja_abc)
        filtro_abc.addStretch()

        painel_abc.corpo.addLayout(filtro_abc)

        self.tabela_abc = QTableWidget()
        self.tabela_abc.setColumnCount(5)
        self.tabela_abc.setHorizontalHeaderLabels(
            ["Produto", "Quantidade", "Total", "% Acumulado", "Classe"]
        )
        self._estilizar_tabela(self.tabela_abc)
        self.tabela_abc.setMinimumHeight(260)
        painel_abc.corpo.addWidget(self.tabela_abc)

        layout.addWidget(painel_abc)

        # ==========================================
        # COMPARATIVO DE ESTOQUE ENTRE LOJAS
        # ==========================================
        painel_comparativo_estoque = PainelSecao(
            "🏬", "Comparativo de Estoque entre Lojas"
        )

        self.tabela_comparativo_estoque = QTableWidget()
        self.tabela_comparativo_estoque.setColumnCount(4)
        self.tabela_comparativo_estoque.setHorizontalHeaderLabels(
            ["Loja", "Quantidade Total", "Valor em Estoque", "Abaixo do Mínimo"]
        )
        self._estilizar_tabela(self.tabela_comparativo_estoque)
        self.tabela_comparativo_estoque.setMinimumHeight(150)
        painel_comparativo_estoque.corpo.addWidget(self.tabela_comparativo_estoque)

        layout.addWidget(painel_comparativo_estoque)

        # ==========================================
        # SUGESTÃO DE REPOSIÇÃO
        # ==========================================
        painel_reposicao = PainelSecao("🔄", "Sugestão de Reposição")

        subtitulo_reposicao = QLabel(
            "Esboço v1: lista quem está no mínimo ou abaixo e sugere "
            "completar até o mínimo -- não considera prazo de entrega "
            "do fornecedor nem sazonalidade, e não gera pedido nenhum "
            "sozinho."
        )
        subtitulo_reposicao.setWordWrap(True)
        subtitulo_reposicao.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; border:none;"
        )
        painel_reposicao.corpo.addWidget(subtitulo_reposicao)

        filtro_reposicao = QHBoxLayout()
        filtro_reposicao.setSpacing(8)

        self.combo_loja_reposicao = QComboBox()
        self.combo_loja_reposicao.setMinimumHeight(36)
        self.combo_loja_reposicao.setCursor(Qt.PointingHandCursor)
        self.combo_loja_reposicao.setStyleSheet(self.combo_periodo_abc.styleSheet())
        self._carregar_combo_lojas(self.combo_loja_reposicao)
        self.combo_loja_reposicao.currentIndexChanged.connect(
            self._atualizar_sugestao_reposicao
        )

        filtro_reposicao.addWidget(self.combo_loja_reposicao)
        filtro_reposicao.addStretch()

        painel_reposicao.corpo.addLayout(filtro_reposicao)

        self.tabela_reposicao = QTableWidget()
        self.tabela_reposicao.setColumnCount(4)
        self.tabela_reposicao.setHorizontalHeaderLabels(
            ["Produto", "Atual", "Mínimo", "Sugestão"]
        )
        self._estilizar_tabela(self.tabela_reposicao)
        self.tabela_reposicao.setMinimumHeight(220)
        painel_reposicao.corpo.addWidget(self.tabela_reposicao)

        layout.addWidget(painel_reposicao)

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
            "CRITICO": tokens.ALERTA_TEXTO,
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
    # CURVA ABC
    # ==========================================

    def _atualizar_curva_abc(self):
        data_inicio, data_fim = self._calcular_periodo(self.combo_periodo_abc)
        loja_id = self.combo_loja_abc.currentData()

        rodar_em_thread(
            self,
            curva_abc,
            data_inicio,
            data_fim,
            loja_id,
            ao_sucesso=self._ao_atualizar_curva_abc_sucesso,
            ao_erro=self._ao_atualizar_secao_secundaria_erro,
        )

    def _ao_atualizar_curva_abc_sucesso(self, itens):

        cores_classe = {
            "A": tokens.SECUNDARIA_HOVER,
            "B": tokens.ALERTA_TEXTO,
            "C": tokens.ERRO,
        }

        self.tabela_abc.setRowCount(len(itens))

        for linha, item in enumerate(itens):
            self.tabela_abc.setItem(
                linha, 0, QTableWidgetItem(item["produto"])
            )
            self.tabela_abc.setItem(
                linha, 1, QTableWidgetItem(str(item["quantidade"]))
            )
            self.tabela_abc.setItem(
                linha, 2, QTableWidgetItem(formatar_moeda(item["total"]))
            )
            self.tabela_abc.setItem(
                linha, 3,
                QTableWidgetItem(f"{item['percentual_acumulado']:.1f}%"),
            )

            item_classe = QTableWidgetItem(item["classe"])
            item_classe.setForeground(
                QColor(cores_classe.get(item["classe"], tokens.TEXTO))
            )
            self.tabela_abc.setItem(linha, 4, item_classe)

    # ==========================================
    # COMPARATIVO DE ESTOQUE ENTRE LOJAS
    # ==========================================

    def _atualizar_comparativo_estoque(self):
        rodar_em_thread(
            self,
            comparativo_estoque,
            ao_sucesso=self._ao_atualizar_comparativo_estoque_sucesso,
            ao_erro=self._ao_atualizar_secao_secundaria_erro,
        )

    def _ao_atualizar_comparativo_estoque_sucesso(self, itens):

        self.tabela_comparativo_estoque.setRowCount(len(itens))

        for linha, item in enumerate(itens):
            self.tabela_comparativo_estoque.setItem(
                linha, 0, QTableWidgetItem(item["loja_nome"])
            )
            self.tabela_comparativo_estoque.setItem(
                linha, 1, QTableWidgetItem(str(item["quantidade_total"]))
            )
            self.tabela_comparativo_estoque.setItem(
                linha, 2,
                QTableWidgetItem(formatar_moeda(item["valor_em_estoque"])),
            )
            self.tabela_comparativo_estoque.setItem(
                linha, 3, QTableWidgetItem(str(item["produtos_abaixo_minimo"]))
            )

    # ==========================================
    # SUGESTÃO DE REPOSIÇÃO
    # ==========================================

    def _atualizar_sugestao_reposicao(self):
        loja_id = self.combo_loja_reposicao.currentData()

        rodar_em_thread(
            self,
            sugestao_reposicao,
            loja_id,
            ao_sucesso=self._ao_atualizar_sugestao_reposicao_sucesso,
            ao_erro=self._ao_atualizar_secao_secundaria_erro,
        )

    def _ao_atualizar_sugestao_reposicao_sucesso(self, itens):

        self.tabela_reposicao.setRowCount(len(itens))

        for linha, item in enumerate(itens):
            self.tabela_reposicao.setItem(
                linha, 0, QTableWidgetItem(item["produto"])
            )
            self.tabela_reposicao.setItem(
                linha, 1, QTableWidgetItem(str(item["quantidade_atual"]))
            )
            self.tabela_reposicao.setItem(
                linha, 2, QTableWidgetItem(str(item["estoque_minimo"]))
            )
            self.tabela_reposicao.setItem(
                linha, 3, QTableWidgetItem(str(item["quantidade_sugerida"]))
            )

    def _ao_atualizar_secao_secundaria_erro(self, erro):
        # secoes secundarias (curva ABC, comparativos, reposicao) -- um
        # erro numa delas nao deveria travar a aba inteira com um
        # QMessageBox bloqueante, so essa secao fica vazia (tabela ja
        # comeca vazia, entao nao precisa nem limpar).
        pass

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

        if self._carregando:
            return
        self._carregando = True

        rodar_em_thread(
            self,
            _buscar_dados_relatorio_geral,
            self.combo_loja_caixa.currentData(),
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _ao_carregar_sucesso(self, resultado):
        self.produtos, self.caixas = resultado
        self._atualizar_financeiro()
        self._atualizar_caixa()
        self._atualizar_estoque()
        self._atualizar_curva_abc()
        self._atualizar_comparativo_estoque()
        self._atualizar_sugestao_reposicao()

    def _ao_carregar_erro(self, erro):
        Mensagem.erro(
            self, f"Não foi possível carregar os dados do relatório.\n{erro}"
        )

    def _ao_carregar_finalizado(self):
        self._carregando = False

    def _recarregar_historico_caixa(self):

        if self._carregando_caixa:
            return
        self._carregando_caixa = True

        rodar_em_thread(
            self,
            historico_caixa,
            self.combo_loja_caixa.currentData(),
            ao_sucesso=self._ao_recarregar_caixa_sucesso,
            ao_erro=self._ao_recarregar_caixa_erro,
            ao_finalizar=self._ao_recarregar_caixa_finalizado,
        )

    def _ao_recarregar_caixa_sucesso(self, caixas):
        self.caixas = caixas
        self._atualizar_caixa()

    def _ao_recarregar_caixa_erro(self, erro):
        Mensagem.erro(
            self, f"Não foi possível carregar o histórico de caixa.\n{erro}"
        )

    def _ao_recarregar_caixa_finalizado(self):
        self._carregando_caixa = False
