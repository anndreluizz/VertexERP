from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QHeaderView,
    QFrame,
)

from services.worker import rodar_em_thread
from design import tokens
from design.icons import icone
from design.widgets import BotaoSecundario
from widgets.dialogs.message_dialog import Mensagem
from telas.relatorios.caixa import CaixaMixin
from telas.relatorios.comum import _buscar_dados_relatorio_geral
from telas.relatorios.estoque import EstoqueMixin
from telas.relatorios.financeiro import FinanceiroMixin
from telas.relatorios.indicadores import IndicadoresMixin
from telas.relatorios.mes_a_mes import MesAMesMixin
from telas.relatorios.widgets import _AlinhaNumeros


class Relatorios(FinanceiroMixin, CaixaMixin, EstoqueMixin, IndicadoresMixin, MesAMesMixin, QWidget):

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
        self._aba_atual = 0
        self._ultimo_relatorio_financeiro = None
        self._indicadores_carregados = False
        self._carregando_indicadores = False

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
        self.bt_imprimir.clicked.connect(self.imprimir_relatorio_financeiro)
        cabecalho.addWidget(self.bt_imprimir)

        layout.addLayout(cabecalho)

        # ======================
        # ABAS
        # ======================

        barra_abas = QFrame()
        barra_abas.setObjectName("barraAbas")
        barra_abas.setStyleSheet(f"""
            QFrame#barraAbas {{
                background:{tokens.BORDA}; border-radius:{tokens.RADIUS_MD}px;
            }}
        """)
        abas_layout = QHBoxLayout(barra_abas)
        abas_layout.setContentsMargins(4, 4, 4, 4)
        abas_layout.setSpacing(4)

        self.bt_aba_financeiro = self._botao_aba("Financeiro", "dollar-sign")
        self.bt_aba_caixa = self._botao_aba("Caixa", "wallet")
        self.bt_aba_estoque = self._botao_aba("Estoque", "package")
        self.bt_aba_indicadores = self._botao_aba("Indicadores", "bar-chart-2")
        self.bt_aba_mes_a_mes = self._botao_aba("Mês a mês", "calendar")

        self.bt_aba_financeiro.clicked.connect(
            lambda: self._selecionar_aba(0)
        )
        self.bt_aba_caixa.clicked.connect(
            lambda: self._selecionar_aba(1)
        )
        self.bt_aba_estoque.clicked.connect(
            lambda: self._selecionar_aba(2)
        )
        self.bt_aba_indicadores.clicked.connect(
            lambda: self._selecionar_aba(3)
        )
        self.bt_aba_mes_a_mes.clicked.connect(
            lambda: self._selecionar_aba(4)
        )

        abas_layout.addWidget(self.bt_aba_financeiro)
        abas_layout.addWidget(self.bt_aba_caixa)
        abas_layout.addWidget(self.bt_aba_estoque)
        abas_layout.addWidget(self.bt_aba_indicadores)
        abas_layout.addWidget(self.bt_aba_mes_a_mes)

        linha_abas = QHBoxLayout()
        linha_abas.addWidget(barra_abas)
        linha_abas.addStretch()
        layout.addLayout(linha_abas)

        self.botoes_aba = [
            self.bt_aba_financeiro,
            self.bt_aba_caixa,
            self.bt_aba_estoque,
            self.bt_aba_indicadores,
            self.bt_aba_mes_a_mes,
        ]

        # ======================
        # PÁGINAS
        # ======================

        self.pagina_financeiro = self._criar_pagina_financeiro()
        self.pagina_caixa = self._criar_pagina_caixa()
        self.pagina_estoque = self._criar_pagina_estoque()
        self.pagina_indicadores = self._criar_pagina_indicadores()
        self.pagina_mes_a_mes = self._criar_pagina_mes_a_mes()

        layout.addWidget(self.pagina_financeiro)
        layout.addWidget(self.pagina_caixa)
        layout.addWidget(self.pagina_estoque)
        layout.addWidget(self.pagina_indicadores)
        layout.addWidget(self.pagina_mes_a_mes)

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

    def _botao_aba(self, texto, icone_nome=None):

        botao = QPushButton(texto)
        botao.setCheckable(True)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setMinimumHeight(38)
        botao.icone_nome = icone_nome
        botao.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; border-radius:{tokens.RADIUS_SM}px;
                color:{tokens.TEXTO_SECUNDARIO}; font-size:{tokens.TAMANHO_MD}px;
                font-weight:700; padding:0 18px;
            }}
            QPushButton:hover {{ color:{tokens.TEXTO}; }}
            QPushButton:checked {{ background:{tokens.CARD}; color:{tokens.PRIMARIA}; }}
        """)
        return botao

    def _selecionar_aba(self, indice):

        paginas = [
            self.pagina_financeiro,
            self.pagina_caixa,
            self.pagina_estoque,
            self.pagina_indicadores,
            self.pagina_mes_a_mes,
        ]

        for i, botao in enumerate(self.botoes_aba):
            botao.setChecked(i == indice)
            if getattr(botao, "icone_nome", None):
                cor = tokens.PRIMARIA if i == indice else tokens.TEXTO_SECUNDARIO
                botao.setIcon(icone(botao.icone_nome, cor=cor, tamanho=16))

        for i, pagina in enumerate(paginas):
            pagina.setVisible(i == indice)

        self._aba_atual = indice

        if indice == 3 and not self._indicadores_carregados:
            self._atualizar_indicadores()

        if indice == 4 and not self._mes_a_mes_carregado:
            self._atualizar_mes_a_mes()

        # por ora so' a aba Centro Financeiro tem um relatorio pra
        # imprimir de verdade (ver imprimir_relatorio_financeiro) --
        # Caixa/Estoque/Indicadores ficam pra uma proxima onda
        # botão cinza em aba que não imprime parecia defeito -- some
        self.bt_imprimir.setVisible(indice == 0)

    # ==========================================
    # ESTILO COMPARTILHADO DE TABELA
    # ==========================================

    def _estilizar_tabela(self, tabela):

        tabela.setItemDelegate(_AlinhaNumeros(tabela))
        tabela.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        tabela.horizontalHeader().setHighlightSections(False)
        tabela.verticalHeader().setDefaultSectionSize(44)
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

        tabela.setAlternatingRowColors(False)
        tabela.setStyleSheet(f"""
            QTableWidget {{
                border: 1.5px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                font-size: {tokens.TAMANHO_MD}px;
            }}
            QTableWidget::item {{
                padding: 0 12px; border-bottom: 1px solid {tokens.BORDA};
            }}
            QTableWidget::item:hover {{ background: {tokens.FUNDO}; }}
            QTableWidget::item:selected {{
                background: {tokens.PRIMARIA_CLARA};
                color: {tokens.PRIMARIA};
            }}
            QHeaderView::section {{
                background: {tokens.FUNDO};
                color: {tokens.TEXTO_SECUNDARIO};
                font-weight: 800;
                font-size: {tokens.TAMANHO_XS}px;
                padding: 8px 12px;
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
        self._atualizar_entradas()
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
