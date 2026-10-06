import re
from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QStyledItemDelegate,
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

from services import comprovante_service
from services.api import configuracoes
from services.relatorio_service import (
    relatorio_vendas,
    curva_abc,
    funil_vendas,
    margem_categoria,
    estoque_categoria,
    vendas_dia_semana,
    vendas_dia_semana_hora,
    gasto_compras_mensal,
    ranking_fornecedores,
    prazo_fornecedores,
    categorias_sem_venda,
    comparativo_lojas,
    comparativo_estoque,
    sugestao_reposicao,
)
from services.produto_service import listar_produtos
from services.caixa_service import historico_caixa
from services.loja_service import listar_lojas
from services.cliente_service import listar_clientes
from services.movimento_fiado_service import listar_movimentos
from services.user_service import listar_usuarios
from services import cliente_analise
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


_LIMIAR_INADIMPLENTE_ALTO = 500  # ver pergunta original do usuario


def _buscar_dados_indicadores(data_inicio, data_fim, loja_id):
    """Roda na worker thread -- chamadas independentes em paralelo,
    mais a agregacao de aging/limite de credito/funcionarios por loja
    (aging/limite reaproveitam cliente_analise, a mesma logica ja
    usada em telas/clientes.py, pra "inadimplente" nunca divergir
    entre as duas telas)."""

    (
        margens, estoques, dias_semana, heatmap_dia_hora, gasto_compras,
        fornecedores, prazos, categorias_paradas, clientes, movimentos,
        usuarios, lojas,
    ) = em_paralelo(
        (margem_categoria, data_inicio, data_fim, loja_id),
        (estoque_categoria, loja_id),
        (vendas_dia_semana, data_inicio, data_fim, loja_id),
        (vendas_dia_semana_hora, data_inicio, data_fim, loja_id),
        (gasto_compras_mensal, data_inicio, data_fim),
        (ranking_fornecedores, data_inicio, data_fim),
        (prazo_fornecedores,),
        (categorias_sem_venda,),
        (listar_clientes, loja_id),
        (listar_movimentos,),
        (listar_usuarios,),
        (listar_lojas,),
    )

    movimentos_por_cliente = {}
    for mov in movimentos:
        cid = mov.get("cliente_id")
        if cid is not None:
            movimentos_por_cliente.setdefault(cid, []).append(mov)

    agregados = [
        cliente_analise.calcular_agregados(
            cliente, movimentos_por_cliente.get(cliente["id"], [])
        )
        for cliente in clientes
    ]

    inadimplentes = [
        agr for agr in agregados if cliente_analise.eh_inadimplente(agr)
    ]

    aging = {"91-120": 0, "121-180": 0, "180+": 0}
    for agr in inadimplentes:
        dias = agr["dias_sem_movimentacao"]
        if dias <= 120:
            aging["91-120"] += 1
        elif dias <= 180:
            aging["121-180"] += 1
        else:
            aging["180+"] += 1

    inadimplentes_valor_alto = sum(
        1 for agr in inadimplentes
        if agr["saldo_devedor"] >= _LIMIAR_INADIMPLENTE_ALTO
    )

    clientes_com_limite = sum(
        1 for c in clientes if float(c.get("limite_credito") or 0) > 0
    )

    nome_loja_por_id = {loja["id"]: loja["nome"] for loja in lojas}
    usuarios_por_loja: dict[str, int] = {}
    for usuario in usuarios:
        nome = nome_loja_por_id.get(usuario.get("loja_id"), "Sem loja definida")
        usuarios_por_loja[nome] = usuarios_por_loja.get(nome, 0) + 1

    return {
        "margem_categoria": margens,
        "estoque_categoria": estoques,
        "vendas_dia_semana": dias_semana,
        "heatmap_dia_hora": heatmap_dia_hora,
        "gasto_compras_mensal": gasto_compras,
        "ranking_fornecedores": fornecedores,
        "prazo_fornecedores": prazos,
        "categorias_sem_venda": categorias_paradas,
        "aging_inadimplencia": aging,
        "total_inadimplentes": len(inadimplentes),
        "inadimplentes_valor_alto": inadimplentes_valor_alto,
        "inadimplentes_valor_baixo": len(inadimplentes) - inadimplentes_valor_alto,
        "clientes_com_limite": clientes_com_limite,
        "clientes_sem_limite": len(clientes) - clientes_com_limite,
        "usuarios_por_loja": usuarios_por_loja,
    }


from design import tokens
from design.charts import GraficoArea, GraficoPizza, GraficoHeatmap
from design.icons import icone, icone_pixmap
from design.widgets import BotaoSecundario, CardKPI, SecaoCard, cor_forma_pagamento
from utils.formatacao import formatar_moeda
from utils.documento_html import (
    ESTILO_BODY,
    bloco_total,
    cabecalho_html,
    cabecalho_tabela,
    linha_zebra,
    rodape_nao_fiscal,
)
from widgets.dialogs.message_dialog import Mensagem


NOMES_FORMA_PAGAMENTO = {
    "DINHEIRO": "Dinheiro",
    "PIX": "PIX",
    "DEBITO": "Débito",
    "CREDITO": "Crédito",
    "BOLETO": "Boleto",
    "PRAZO": "Crediário",
}

class _CoresFormaPagamento:
    """Mesmas cores do PDV/fiado/despesa (cor_forma_pagamento) -- antes
    era um dict fixo aqui com outra paleta (Débito laranja, PIX azul) e
    calculado no import, antes do tema escuro existir. Mantém o .get()
    porque telas/dashboard.py usa CORES_FORMA_PAGAMENTO.get(forma, cor)."""

    def get(self, forma, _padrao=None):
        return cor_forma_pagamento(forma)

    def __getitem__(self, forma):
        return cor_forma_pagamento(forma)


CORES_FORMA_PAGAMENTO = _CoresFormaPagamento()

# ícone do sistema no lugar dos emojis antigos (que viravam quadrado em
# máquina sem fonte de emoji e destoavam do resto do sistema) --
# PainelSecao continua aceitando o emoji pra não quebrar quem chama
_ICONE_POR_EMOJI = {
    "\U0001f4c8": "trending-up", "\U0001f4e6": "package", "\U0001f4b3": "credit-card",
    "\U0001f53b": "filter", "\U0001f3ec": "store", "\U0001f504": "refresh-cw",
    "\U0001f4b0": "dollar-sign", "\U0001f4c5": "calendar", "\U0001f525": "bar-chart-2",
    "\U0001f6d2": "shopping-cart", "\U0001f3ed": "truck", "\u23f1\ufe0f": "calendar",
    "\U0001f40c": "alert-triangle", "\U0001f534": "alert-triangle", "\U0001f3af": "star",
    "\U0001f465": "users", "\U0001f550": "calendar",
}

_NUMERO = re.compile(r"^[\s+\-−–R$]*[\d.,]+\s*(%|x|un\.?|dias?)?$")


class _AlinhaNumeros(QStyledItemDelegate):
    """Valor (R$, %, quantidade) alinhado à direita, como em planilha --
    e o cabeçalho da coluna acompanha. Vale pra toda tabela que passa
    por _estilizar_tabela, sem mexer em cada lugar que preenche célula."""

    def __init__(self, tabela):
        super().__init__(tabela)
        self._tabela = tabela
        self._colunas_numericas = set()

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        texto = str(index.data() or "").strip()
        if texto and texto != "—" and _NUMERO.match(texto):
            option.displayAlignment = Qt.AlignRight | Qt.AlignVCenter
            coluna = index.column()
            if coluna not in self._colunas_numericas:
                self._colunas_numericas.add(coluna)
                cabecalho = self._tabela.horizontalHeaderItem(coluna)
                if cabecalho is not None:
                    cabecalho.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)


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

        self.setObjectName("painelSecao")
        self.setStyleSheet(f"""
            QFrame#painelSecao {{
                background:{tokens.CARD};
                border-radius:{tokens.RADIUS_LG}px;
                border:1px solid {tokens.BORDA};
            }}
        """)

        self.layout_externo = QVBoxLayout(self)
        self.layout_externo.setContentsMargins(20, 18, 20, 18)
        self.layout_externo.setSpacing(12)

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(10)

        nome_icone = _ICONE_POR_EMOJI.get(icone, icone if icone.isascii() else "bar-chart-2")
        lbl_icone = QLabel()
        lbl_icone.setFixedSize(30, 30)
        lbl_icone.setAlignment(Qt.AlignCenter)
        lbl_icone.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; border:none;
            border-radius:{tokens.RADIUS_SM}px;
        """)
        lbl_icone.setPixmap(icone_pixmap(nome_icone, cor=tokens.PRIMARIA, tamanho=16))

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

        abas_layout.addWidget(self.bt_aba_financeiro)
        abas_layout.addWidget(self.bt_aba_caixa)
        abas_layout.addWidget(self.bt_aba_estoque)
        abas_layout.addWidget(self.bt_aba_indicadores)

        linha_abas = QHBoxLayout()
        linha_abas.addWidget(barra_abas)
        linha_abas.addStretch()
        layout.addLayout(linha_abas)

        self.botoes_aba = [
            self.bt_aba_financeiro,
            self.bt_aba_caixa,
            self.bt_aba_estoque,
            self.bt_aba_indicadores,
        ]

        # ======================
        # PÁGINAS
        # ======================

        self.pagina_financeiro = self._criar_pagina_financeiro()
        self.pagina_caixa = self._criar_pagina_caixa()
        self.pagina_estoque = self._criar_pagina_estoque()
        self.pagina_indicadores = self._criar_pagina_indicadores()

        layout.addWidget(self.pagina_financeiro)
        layout.addWidget(self.pagina_caixa)
        layout.addWidget(self.pagina_estoque)
        layout.addWidget(self.pagina_indicadores)

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

        # por ora so' a aba Centro Financeiro tem um relatorio pra
        # imprimir de verdade (ver imprimir_relatorio_financeiro) --
        # Caixa/Estoque/Indicadores ficam pra uma proxima onda
        # botão cinza em aba que não imprime parecia defeito -- some
        self.bt_imprimir.setVisible(indice == 0)

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
        self.card_lucro = CardKPI("Lucro", "trending-up", tokens.SECUNDARIA)
        self.card_volume = CardKPI("Vendas", "shopping-cart", tokens.PRIMARIA)
        self.card_ticket = CardKPI("Ticket Médio", "bar-chart-2", tokens.ALERTA)

        for card in (self.card_faturamento, self.card_lucro, self.card_volume, self.card_ticket):
            cards_layout.addWidget(card, 1)

        layout.addLayout(cards_layout)

        painel_tendencia = PainelSecao("📈", "Faturamento no Período")
        self.grafico_tendencia = GraficoArea()
        painel_tendencia.corpo.addWidget(self.grafico_tendencia)
        layout.addWidget(painel_tendencia)

        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(16)

        self.painel_ranking = PainelSecao("📦", "Ranking de Produtos")
        self.painel_mix = PainelSecao("💳", "Mix de Pagamentos")

        self.grafico_mix = GraficoPizza()
        self.grafico_mix.setFixedHeight(140)
        # entra entre o cabecalho do painel e o corpo (lista de
        # LinhaBarra) -- fora de self.painel_mix.corpo de proposito,
        # pra nao ser apagado toda vez que _atualizar_mix_pagamentos
        # chama limpar_corpo()
        self.painel_mix.layout_externo.insertWidget(1, self.grafico_mix)

        grid_layout.addWidget(self.painel_ranking, stretch=1)
        grid_layout.addWidget(self.painel_mix, stretch=1)

        layout.addLayout(grid_layout)

        self.painel_funil = PainelSecao("🔻", "Funil de Vendas")

        subtitulo_funil = QLabel(
            "Carrinhos em aberto é uma contagem ao vivo (agora), sem "
            "recorte de período — rascunhos excluídos não deixam "
            "rastro. Finalizadas/canceladas são do período selecionado "
            "acima."
        )
        subtitulo_funil.setWordWrap(True)
        subtitulo_funil.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; border:none;"
        )
        # fora de self.painel_funil.corpo de proposito -- mesmo motivo
        # do self.grafico_mix acima, corpo e' limpo a cada refresh
        self.painel_funil.layout_externo.insertWidget(1, subtitulo_funil)

        layout.addWidget(self.painel_funil)

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

        rodar_em_thread(
            self,
            funil_vendas,
            inicio.isoformat() if inicio else None,
            fim.isoformat(),
            ao_sucesso=self._ao_atualizar_funil_sucesso,
            ao_erro=self._ao_atualizar_secao_secundaria_erro,
        )

    def _ao_atualizar_funil_sucesso(self, dados):

        self.painel_funil.limpar_corpo()

        maior_valor = max(
            dados["suspensas_agora"], dados["finalizadas"], dados["canceladas"], 1
        )

        self.painel_funil.corpo.addWidget(LinhaBarra(
            "Carrinhos em aberto agora",
            None,
            str(dados["suspensas_agora"]),
            dados["suspensas_agora"] / maior_valor * 100,
            tokens.TEXTO_SECUNDARIO,
        ))
        self.painel_funil.corpo.addWidget(LinhaBarra(
            "Vendas finalizadas",
            "no período selecionado",
            str(dados["finalizadas"]),
            dados["finalizadas"] / maior_valor * 100,
            tokens.SECUNDARIA_HOVER,
        ))
        self.painel_funil.corpo.addWidget(LinhaBarra(
            "Vendas canceladas",
            f"{float(dados['taxa_cancelamento']):.1f}".replace(".", ",") + "% das vendas do período",
            str(dados["canceladas"]),
            dados["canceladas"] / maior_valor * 100,
            tokens.ERRO,
        ))

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

    def imprimir_relatorio_financeiro(self):

        if self._aba_atual != 0:
            return

        if not self._ultimo_relatorio_financeiro:
            Mensagem.erro(
                self, "Aguarde o relatório financeiro carregar antes de imprimir."
            )
            return

        relatorio = self._ultimo_relatorio_financeiro

        linhas_produtos = "".join(
            linha_zebra(
                [item["produto"], item["quantidade"], formatar_moeda(item["total"])],
                indice,
                alinhamentos=["left", "center", "right"],
            )
            for indice, item in enumerate(relatorio["top_produtos"])
        ) or linha_zebra(["Nenhuma venda no período.", "", ""], 0)

        linhas_pagamento = "".join(
            linha_zebra(
                [
                    NOMES_FORMA_PAGAMENTO.get(item["forma_pagamento"], item["forma_pagamento"]),
                    item["quantidade"],
                    formatar_moeda(item["total"]),
                ],
                indice,
                alinhamentos=["left", "center", "right"],
            )
            for indice, item in enumerate(relatorio["formas_pagamento"])
        ) or linha_zebra(["Nenhuma venda no período.", "", ""], 0)

        periodo_texto = self.combo_periodo.currentText()
        loja_texto = self.combo_loja.currentText()

        html = f"""
        <html>
        <body style="{ESTILO_BODY}">
            {cabecalho_html(
                "RELATÓRIO FINANCEIRO",
                configuracoes(),
                comprovante_service.obter_logo_loja(),
            )}
            <p style="margin:4px 0;">Período: {periodo_texto}</p>
            <p style="margin:4px 0;">Loja: {loja_texto}</p>
            <p style="margin:4px 0;">
                Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </p>
            <h4 style="margin:16px 0 6px; color:#1E293B;">RANKING DE PRODUTOS</h4>
            <table style="width:100%; border-collapse:collapse; border:1px solid #E5E7EB;">
                {cabecalho_tabela(
                    ["Produto", "Qtd", "Total"], ["left", "center", "right"]
                )}
                {linhas_produtos}
            </table>
            <h4 style="margin:16px 0 6px; color:#1E293B;">MIX DE PAGAMENTOS</h4>
            <table style="width:100%; border-collapse:collapse; border:1px solid #E5E7EB;">
                {cabecalho_tabela(
                    ["Forma", "Qtd", "Total"], ["left", "center", "right"]
                )}
                {linhas_pagamento}
            </table>
            {bloco_total(
                "FATURAMENTO BRUTO",
                formatar_moeda(float(relatorio["receita_total"]["atual"])),
            )}
            {rodape_nao_fiscal("Relatório interno -- não possui valor fiscal.")}
        </body>
        </html>
        """

        comprovante_service.imprimir(html, self)

    def _ao_atualizar_financeiro_sucesso(self, relatorio):

        self._ultimo_relatorio_financeiro = relatorio

        faturamento = float(relatorio["receita_total"]["atual"])
        volume = int(relatorio["quantidade_vendas"]["atual"])
        ticket_medio = float(relatorio["ticket_medio"]["atual"])
        lucro = float((relatorio.get("lucro") or {}).get("atual") or 0)
        margem = float((relatorio.get("margem_lucro") or {}).get("atual") or 0)

        self.card_faturamento.definir_valor(formatar_moeda(faturamento))
        self.card_lucro.definir_valor(formatar_moeda(lucro))
        self.card_volume.definir_valor(str(volume))
        self.card_ticket.definir_valor(formatar_moeda(ticket_medio))

        # variação contra o período anterior de mesmo tamanho (o backend
        # manda None quando não tem base -- aí o selo some)
        for card, chave in (
            (self.card_faturamento, "receita_total"), (self.card_lucro, "lucro"),
            (self.card_volume, "quantidade_vendas"), (self.card_ticket, "ticket_medio"),
        ):
            variacao = (relatorio.get(chave) or {}).get("variacao_pct")
            card.definir_variacao(variacao, "vs período anterior")
            if variacao is None:
                card.definir_legenda("sem período anterior pra comparar")

        self.card_lucro.definir_legenda(f"margem de {margem:.1f}%".replace(".", ","))

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

        totais = {item["data"]: float(item["total"]) for item in vendas_por_dia}

        # o backend só manda dia que teve venda -- sem completar com zero
        # o gráfico pulava os dias parados (e com 1 dia só nem desenhava)
        inicio, fim = self._periodo_selecionado()
        if inicio is None:
            inicio = datetime.strptime(min(totais), "%Y-%m-%d").date()
        dias = []
        if (fim - inicio).days <= 92:
            dia = inicio
            while dia <= fim:
                dias.append(dia)
                dia += timedelta(days=1)
        else:
            dias = [datetime.strptime(d, "%Y-%m-%d").date() for d in sorted(totais)]

        for dia in dias:
            rotulos.append(dia.strftime("%d/%m"))
            rotulos_completos.append(dia.strftime("%d/%m/%Y"))
            valores.append(totais.get(dia.strftime("%Y-%m-%d"), 0.0))

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

        self.grafico_mix.definir_dados([
            (
                float(item["total"]),
                CORES_FORMA_PAGAMENTO.get(item["forma_pagamento"], tokens.TEXTO),
            )
            for item in formas_pagamento
        ])

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
                f"{percentual:.1f}".replace(".", ",") + "% do total",
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

        titulo = QLabel("Histórico de caixas")
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

        cards_caixa = QHBoxLayout()
        cards_caixa.setSpacing(14)
        self.card_caixas_total = CardKPI("Caixas no histórico", "wallet", tokens.PRIMARIA)
        self.card_caixas_diferenca = CardKPI("Fechados com diferença", "alert-triangle", tokens.ALERTA)
        self.card_diferenca_total = CardKPI("Diferença acumulada", "dollar-sign", tokens.ERRO)
        for card in (self.card_caixas_total, self.card_caixas_diferenca, self.card_diferenca_total):
            cards_caixa.addWidget(card, 1)
        layout.addLayout(cards_caixa)

        self.tabela_caixa = QTableWidget()
        self.tabela_caixa.setColumnCount(7)
        self.tabela_caixa.setHorizontalHeaderLabels([
            "Abertura",
            "Fechamento",
            "Troco inicial",
            "Esperado",
            "Contado",
            "Diferença",
            "Situação",
        ])
        self._estilizar_tabela(self.tabela_caixa)

        self.tabela_caixa.setMinimumHeight(360)
        layout.addWidget(self.tabela_caixa)
        layout.addStretch()

        return pagina

    @staticmethod
    def _data_hora(texto):
        try:
            return datetime.fromisoformat(texto).strftime("%d/%m/%Y %H:%M")
        except (ValueError, TypeError):
            return texto or "—"

    def _atualizar_caixa(self):

        self.tabela_caixa.setRowCount(0)

        fechados_com_diferenca = 0
        diferenca_total = 0.0

        for caixa in self.caixas:

            linha = self.tabela_caixa.rowCount()
            self.tabela_caixa.insertRow(linha)

            aberto = caixa.get("status") == "ABERTO"
            esperado = caixa.get("saldo_final")
            contado = caixa.get("valor_contado")

            diferenca = None
            if not aberto and esperado is not None and contado is not None:
                diferenca = float(contado) - float(esperado)
                if abs(diferenca) >= 0.01:
                    fechados_com_diferenca += 1
                    diferenca_total += diferenca

            valores = [
                self._data_hora(caixa.get("data_abertura")),
                "—" if aberto else self._data_hora(caixa.get("data_fechamento")),
                formatar_moeda(caixa.get("saldo_inicial", 0)),
                formatar_moeda(esperado) if esperado is not None else "—",
                formatar_moeda(contado) if contado is not None else "—",
            ]
            for coluna, texto in enumerate(valores):
                self.tabela_caixa.setItem(linha, coluna, QTableWidgetItem(texto))

            if diferenca is None:
                item_dif = QTableWidgetItem("—")
            elif abs(diferenca) < 0.01:
                item_dif = QTableWidgetItem("R$ 0,00")
                item_dif.setForeground(QColor(tokens.SECUNDARIA_HOVER))
            else:
                sinal = "+ " if diferenca > 0 else "− "
                item_dif = QTableWidgetItem(sinal + formatar_moeda(abs(diferenca)))
                item_dif.setForeground(QColor(tokens.PRIMARIA if diferenca > 0 else tokens.ERRO))
            self.tabela_caixa.setItem(linha, 5, item_dif)

            if aberto:
                texto_sit, cor_sit = "● Em aberto", tokens.ALERTA
            elif diferenca is None or abs(diferenca) < 0.01:
                texto_sit, cor_sit = "● Conferido", tokens.SECUNDARIA_HOVER
            else:
                texto_sit = "● Sobra" if diferenca > 0 else "● Falta"
                cor_sit = tokens.PRIMARIA if diferenca > 0 else tokens.ERRO
            item_sit = QTableWidgetItem(texto_sit)
            item_sit.setForeground(QColor(cor_sit))
            self.tabela_caixa.setItem(linha, 6, item_sit)

        self.card_caixas_total.definir_valor(str(len(self.caixas)))
        abertos = sum(1 for c in self.caixas if c.get("status") == "ABERTO")
        self.card_caixas_total.definir_legenda(f"{abertos} em aberto agora")
        self.card_caixas_diferenca.definir_valor(str(fechados_com_diferenca))
        self.card_caixas_diferenca.definir_legenda("sobra ou falta na conferência")
        sinal = "+ " if diferenca_total > 0.009 else ("− " if diferenca_total < -0.009 else "")
        self.card_diferenca_total.definir_valor(sinal + formatar_moeda(abs(diferenca_total)))
        self.card_diferenca_total.definir_legenda("contado − esperado, somando tudo")

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

    # ==========================================
    # PÁGINA: INDICADORES
    # ==========================================

    def _criar_pagina_indicadores(self):

        pagina, layout = self._pagina_rolavel(espacamento=12)

        filtro_layout = QHBoxLayout()
        filtro_layout.setSpacing(8)

        self.combo_periodo_indicadores = QComboBox()
        self.combo_periodo_indicadores.addItems(self.PERIODOS)
        self.combo_periodo_indicadores.setCurrentText("Este mês")
        self.combo_periodo_indicadores.setMinimumHeight(36)
        self.combo_periodo_indicadores.setCursor(Qt.PointingHandCursor)
        self.combo_periodo_indicadores.setStyleSheet(f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:4px 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """)

        self.combo_loja_indicadores = QComboBox()
        self.combo_loja_indicadores.setMinimumHeight(36)
        self.combo_loja_indicadores.setCursor(Qt.PointingHandCursor)
        self.combo_loja_indicadores.setStyleSheet(
            self.combo_periodo_indicadores.styleSheet()
        )
        self._carregar_combo_lojas(self.combo_loja_indicadores)

        self._timer_atualizar_indicadores = QTimer(self)
        self._timer_atualizar_indicadores.setSingleShot(True)
        self._timer_atualizar_indicadores.timeout.connect(
            self._atualizar_indicadores
        )
        self.combo_periodo_indicadores.currentTextChanged.connect(
            lambda: self._timer_atualizar_indicadores.start(300)
        )
        self.combo_loja_indicadores.currentIndexChanged.connect(
            lambda: self._timer_atualizar_indicadores.start(300)
        )

        filtro_layout.addWidget(self.combo_periodo_indicadores)
        filtro_layout.addWidget(self.combo_loja_indicadores)
        filtro_layout.addStretch()

        layout.addLayout(filtro_layout)

        # margem por categoria
        painel_margem = PainelSecao("💰", "Margem por Categoria")
        self.tabela_margem_categoria = QTableWidget()
        self.tabela_margem_categoria.setColumnCount(4)
        self.tabela_margem_categoria.setHorizontalHeaderLabels(
            ["Categoria", "Receita", "Lucro", "Margem %"]
        )
        self._estilizar_tabela(self.tabela_margem_categoria)
        self.tabela_margem_categoria.setMinimumHeight(160)
        painel_margem.corpo.addWidget(self.tabela_margem_categoria)
        layout.addWidget(painel_margem)

        # estoque por categoria (nao depende de periodo, so' de loja)
        painel_estoque_cat = PainelSecao("📦", "Estoque por Categoria")
        self.tabela_estoque_categoria = QTableWidget()
        self.tabela_estoque_categoria.setColumnCount(3)
        self.tabela_estoque_categoria.setHorizontalHeaderLabels(
            ["Categoria", "Quantidade", "Valor em Estoque"]
        )
        self._estilizar_tabela(self.tabela_estoque_categoria)
        self.tabela_estoque_categoria.setMinimumHeight(150)
        painel_estoque_cat.corpo.addWidget(self.tabela_estoque_categoria)
        layout.addWidget(painel_estoque_cat)

        # vendas por dia da semana
        self.painel_dia_semana = PainelSecao("📅", "Vendas por Dia da Semana")
        layout.addWidget(self.painel_dia_semana)

        # mapa de calor dia da semana x hora
        painel_heatmap = PainelSecao("🔥", "Quando a Loja Mais Vende")
        self.grafico_heatmap = GraficoHeatmap()
        painel_heatmap.corpo.addWidget(self.grafico_heatmap)
        layout.addWidget(painel_heatmap)

        # gasto mensal com compras
        self.painel_gasto_compras = PainelSecao("🛒", "Gasto Mensal com Compras")
        layout.addWidget(self.painel_gasto_compras)

        # ranking de fornecedores
        painel_fornecedores = PainelSecao("🏭", "Ranking de Fornecedores")
        self.tabela_fornecedores = QTableWidget()
        self.tabela_fornecedores.setColumnCount(3)
        self.tabela_fornecedores.setHorizontalHeaderLabels(
            ["Fornecedor", "Qtd. Compras", "Total"]
        )
        self._estilizar_tabela(self.tabela_fornecedores)
        self.tabela_fornecedores.setMinimumHeight(150)
        painel_fornecedores.corpo.addWidget(self.tabela_fornecedores)
        layout.addWidget(painel_fornecedores)

        # prazo medio de pagamento por fornecedor
        painel_prazo = PainelSecao("⏱️", "Prazo Médio de Pagamento por Fornecedor")
        subtitulo_prazo = QLabel(
            "Só considera compras a prazo (com parcelas geradas em "
            "Contas a Pagar)."
        )
        subtitulo_prazo.setWordWrap(True)
        subtitulo_prazo.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; border:none;"
        )
        painel_prazo.corpo.addWidget(subtitulo_prazo)
        self.tabela_prazo_fornecedores = QTableWidget()
        self.tabela_prazo_fornecedores.setColumnCount(3)
        self.tabela_prazo_fornecedores.setHorizontalHeaderLabels(
            ["Fornecedor", "Prazo Médio", "Qtd. Parcelas"]
        )
        self._estilizar_tabela(self.tabela_prazo_fornecedores)
        self.tabela_prazo_fornecedores.setMinimumHeight(150)
        painel_prazo.corpo.addWidget(self.tabela_prazo_fornecedores)
        layout.addWidget(painel_prazo)

        # categorias sem venda ha muito tempo
        painel_paradas = PainelSecao("🐌", "Categorias Sem Venda Há Mais de 90 Dias")
        self.tabela_categorias_paradas = QTableWidget()
        self.tabela_categorias_paradas.setColumnCount(2)
        self.tabela_categorias_paradas.setHorizontalHeaderLabels(
            ["Categoria", "Última Venda"]
        )
        self._estilizar_tabela(self.tabela_categorias_paradas)
        self.tabela_categorias_paradas.setMinimumHeight(120)
        painel_paradas.corpo.addWidget(self.tabela_categorias_paradas)
        layout.addWidget(painel_paradas)

        # aging de inadimplencia
        self.painel_aging = PainelSecao(
            "🔴", "Inadimplência por Tempo de Atraso e Valor"
        )
        subtitulo_aging = QLabel(
            "Mesmo critério da tela de Clientes: saldo devedor e mais "
            "de 90 dias sem nenhuma movimentação (compra ou pagamento)."
        )
        subtitulo_aging.setWordWrap(True)
        subtitulo_aging.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; border:none;"
        )
        self.painel_aging.layout_externo.insertWidget(1, subtitulo_aging)
        layout.addWidget(self.painel_aging)

        # limite de credito definido
        self.painel_limite_credito = PainelSecao(
            "🎯", "Limite de Crédito Definido"
        )
        layout.addWidget(self.painel_limite_credito)

        # funcionarios (usuarios do sistema) por loja
        self.painel_usuarios_loja = PainelSecao(
            "👥", "Usuários do Sistema por Loja"
        )
        subtitulo_usuarios = QLabel(
            "Contagem de logins, não necessariamente igual ao número "
            "real de funcionários (nem todo funcionário tem login, e "
            "o Vertex não tem módulo de RH/folha)."
        )
        subtitulo_usuarios.setWordWrap(True)
        subtitulo_usuarios.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; "
            f"font-size:{tokens.TAMANHO_XS}px; border:none;"
        )
        self.painel_usuarios_loja.layout_externo.insertWidget(1, subtitulo_usuarios)
        layout.addWidget(self.painel_usuarios_loja)

        layout.addStretch()

        return pagina

    def _atualizar_indicadores(self):

        if self._carregando_indicadores:
            return
        self._carregando_indicadores = True

        data_inicio, data_fim = self._calcular_periodo(
            self.combo_periodo_indicadores
        )
        loja_id = self.combo_loja_indicadores.currentData()

        rodar_em_thread(
            self,
            _buscar_dados_indicadores,
            data_inicio.isoformat() if data_inicio else None,
            data_fim.isoformat(),
            loja_id,
            ao_sucesso=self._ao_atualizar_indicadores_sucesso,
            ao_erro=self._ao_atualizar_indicadores_erro,
            ao_finalizar=self._ao_atualizar_indicadores_finalizado,
        )

    def _ao_atualizar_indicadores_erro(self, erro):
        Mensagem.erro(
            self, f"Não foi possível carregar os indicadores.\n{erro}"
        )

    def _ao_atualizar_indicadores_finalizado(self):
        self._carregando_indicadores = False

    def _ao_atualizar_indicadores_sucesso(self, dados):

        self._indicadores_carregados = True

        # margem por categoria
        margens = dados["margem_categoria"]
        self.tabela_margem_categoria.setRowCount(len(margens))
        for linha, item in enumerate(margens):
            self.tabela_margem_categoria.setItem(
                linha, 0, QTableWidgetItem(item["categoria"])
            )
            self.tabela_margem_categoria.setItem(
                linha, 1, QTableWidgetItem(formatar_moeda(item["receita"]))
            )
            self.tabela_margem_categoria.setItem(
                linha, 2, QTableWidgetItem(formatar_moeda(item["lucro"]))
            )
            self.tabela_margem_categoria.setItem(
                linha, 3, QTableWidgetItem(f"{float(item['margem_pct']):.1f}%".replace(".", ","))
            )

        # estoque por categoria
        estoques = dados["estoque_categoria"]
        self.tabela_estoque_categoria.setRowCount(len(estoques))
        for linha, item in enumerate(estoques):
            self.tabela_estoque_categoria.setItem(
                linha, 0, QTableWidgetItem(item["categoria"])
            )
            self.tabela_estoque_categoria.setItem(
                linha, 1, QTableWidgetItem(str(item["quantidade"]))
            )
            self.tabela_estoque_categoria.setItem(
                linha, 2, QTableWidgetItem(formatar_moeda(item["valor"]))
            )

        # vendas por dia da semana
        self.painel_dia_semana.limpar_corpo()
        dias_semana = dados["vendas_dia_semana"]
        maior_dia = max(
            (float(item["total"]) for item in dias_semana), default=0
        ) or 1

        for item in dias_semana:
            total = float(item["total"])
            self.painel_dia_semana.corpo.addWidget(LinhaBarra(
                item["dia_semana"],
                f"{item['quantidade']} venda(s)",
                formatar_moeda(total),
                total / maior_dia * 100,
                tokens.PRIMARIA,
            ))

        # mapa de calor dia da semana x hora
        self.grafico_heatmap.definir_dados(dados["heatmap_dia_hora"])

        # gasto mensal com compras
        self.painel_gasto_compras.limpar_corpo()
        gasto_compras = dados["gasto_compras_mensal"]

        if not gasto_compras:
            self.painel_gasto_compras.adicionar_vazio(
                "Nenhuma compra registrada no período."
            )
        else:
            maior_mes = max(
                (float(item["total"]) for item in gasto_compras), default=0
            ) or 1
            for item in gasto_compras:
                total = float(item["total"])
                self.painel_gasto_compras.corpo.addWidget(LinhaBarra(
                    item["mes"],
                    None,
                    formatar_moeda(total),
                    total / maior_mes * 100,
                    tokens.SECUNDARIA,
                ))

        # ranking de fornecedores
        fornecedores = dados["ranking_fornecedores"]
        self.tabela_fornecedores.setRowCount(len(fornecedores))
        for linha, item in enumerate(fornecedores):
            self.tabela_fornecedores.setItem(
                linha, 0, QTableWidgetItem(item["nome"])
            )
            self.tabela_fornecedores.setItem(
                linha, 1, QTableWidgetItem(str(item["quantidade_compras"]))
            )
            self.tabela_fornecedores.setItem(
                linha, 2, QTableWidgetItem(formatar_moeda(item["total"]))
            )

        # prazo medio de pagamento por fornecedor
        prazos = dados["prazo_fornecedores"]
        self.tabela_prazo_fornecedores.setRowCount(len(prazos))
        for linha, item in enumerate(prazos):
            self.tabela_prazo_fornecedores.setItem(
                linha, 0, QTableWidgetItem(item["nome"])
            )
            self.tabela_prazo_fornecedores.setItem(
                linha, 1,
                QTableWidgetItem(f"{item['prazo_medio_dias']:.0f} dias"),
            )
            self.tabela_prazo_fornecedores.setItem(
                linha, 2, QTableWidgetItem(str(item["quantidade_parcelas"]))
            )

        # categorias sem venda ha muito tempo
        categorias_paradas = dados["categorias_sem_venda"]
        self.tabela_categorias_paradas.setRowCount(len(categorias_paradas))
        for linha, item in enumerate(categorias_paradas):
            self.tabela_categorias_paradas.setItem(
                linha, 0, QTableWidgetItem(item["categoria"])
            )
            dias_sem_venda = item["dias_sem_venda"]
            texto_ultima = (
                "Nunca vendida" if dias_sem_venda is None
                else f"Há {dias_sem_venda} dias"
            )
            self.tabela_categorias_paradas.setItem(
                linha, 1, QTableWidgetItem(texto_ultima)
            )

        # aging de inadimplencia (tempo de atraso + faixa de valor)
        self.painel_aging.limpar_corpo()
        aging = dados["aging_inadimplencia"]
        total_inadimplentes = dados["total_inadimplentes"]

        if not total_inadimplentes:
            self.painel_aging.adicionar_vazio(
                "Nenhum cliente inadimplente no momento."
            )
        else:
            rotulos_aging = {
                "91-120": "91 a 120 dias",
                "121-180": "121 a 180 dias",
                "180+": "Mais de 180 dias",
            }
            for chave, rotulo in rotulos_aging.items():
                quantidade = aging[chave]
                self.painel_aging.corpo.addWidget(LinhaBarra(
                    rotulo,
                    None,
                    f"{quantidade} cliente(s)",
                    quantidade / total_inadimplentes * 100,
                    tokens.ERRO,
                ))

            limiar_texto = formatar_moeda(_LIMIAR_INADIMPLENTE_ALTO)
            valor_alto = dados["inadimplentes_valor_alto"]
            valor_baixo = dados["inadimplentes_valor_baixo"]

            self.painel_aging.corpo.addWidget(LinhaBarra(
                f"Saldo devedor ≥ {limiar_texto}",
                None,
                f"{valor_alto} cliente(s)",
                valor_alto / total_inadimplentes * 100,
                tokens.ERRO,
            ))
            self.painel_aging.corpo.addWidget(LinhaBarra(
                f"Saldo devedor < {limiar_texto}",
                None,
                f"{valor_baixo} cliente(s)",
                valor_baixo / total_inadimplentes * 100,
                tokens.ALERTA_TEXTO,
            ))

        # limite de credito
        self.painel_limite_credito.limpar_corpo()
        com_limite = dados["clientes_com_limite"]
        sem_limite = dados["clientes_sem_limite"]
        total_clientes = com_limite + sem_limite

        if not total_clientes:
            self.painel_limite_credito.adicionar_vazio(
                "Nenhum cliente cadastrado."
            )
        else:
            self.painel_limite_credito.corpo.addWidget(LinhaBarra(
                "Com limite definido",
                None,
                str(com_limite),
                com_limite / total_clientes * 100,
                tokens.SECUNDARIA_HOVER,
            ))
            self.painel_limite_credito.corpo.addWidget(LinhaBarra(
                "Sem limite definido (\"no olho\")",
                None,
                str(sem_limite),
                sem_limite / total_clientes * 100,
                tokens.ALERTA_TEXTO,
            ))

        # usuarios do sistema por loja
        self.painel_usuarios_loja.limpar_corpo()
        usuarios_por_loja = dados["usuarios_por_loja"]

        if not usuarios_por_loja:
            self.painel_usuarios_loja.adicionar_vazio(
                "Nenhum usuário cadastrado."
            )
        else:
            maior_qtd = max(usuarios_por_loja.values())
            for nome_loja, quantidade in sorted(
                usuarios_por_loja.items(), key=lambda i: i[1], reverse=True
            ):
                self.painel_usuarios_loja.corpo.addWidget(LinhaBarra(
                    nome_loja,
                    None,
                    str(quantidade),
                    quantidade / maior_qtd * 100,
                    tokens.PRIMARIA,
                ))

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
                QTableWidgetItem(f"{item['percentual_acumulado']:.1f}%".replace(".", ",")),
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
