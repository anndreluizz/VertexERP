from datetime import datetime, timedelta

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QMessageBox,
    QScrollArea,
    QFrame,
    QComboBox,
    QPushButton,
    QButtonGroup,
)

from design import tokens
from design.animations import fade_in
from design.icons import icone_pixmap
from design.widgets import CardKPI, SecaoCard, Badge, BotaoSecundario, Card
from design.charts import GraficoArea, LinhaProgresso
from widgets.nav_card import NavCard

from services.api import dashboard, me
from services.venda_service import listar_vendas
from services.produto_service import listar_produtos
from services.conta_pagar_service import listar_contas_pagar
from services.cliente_service import listar_clientes
from services.movimento_fiado_service import listar_movimentos
from services.user_service import listar_usuarios
from services.worker import rodar_em_thread
from services import preferencias_service

from telas.relatorios import NOMES_FORMA_PAGAMENTO, CORES_FORMA_PAGAMENTO
from utils.formatacao import formatar_moeda


DIAS_SEMANA_ABREV = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
DIAS_SEMANA_COMPLETO = [
    "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
    "Sexta-feira", "Sábado", "Domingo",
]
MESES_COMPLETO = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]

VARIANTE_BADGE_FORMA = {
    "DINHEIRO": "sucesso",
    "PIX": "info",
    "DEBITO": "neutro",
    "CREDITO": "neutro",
    "BOLETO": "neutro",
    "PRAZO": "alerta",
}

# opcoes de periodo reaproveitadas pelos combos de Formas de Pagamento
# e Top Produtos -- (rotulo, dias)
OPCOES_PERIODO = [("Hoje", 1), ("7 dias", 7), ("30 dias", 30)]


def _parse_data(texto):
    try:
        return datetime.fromisoformat(texto)
    except (ValueError, TypeError):
        return None


def _variacao_percentual(atual, anterior):
    """None quando não há base de comparação (ex.: ontem sem nenhuma
    venda) -- melhor não mostrar selo nenhum do que inventar um "+∞%"
    ou um "0%" que não significa nada."""

    if not anterior:
        return None

    return ((atual - anterior) / anterior) * 100


def _reordenar_por_preferencia(registro, ordem_salva):
    """Reordena um registro de cards pela ordem salva (lista de ids). Ids
    salvos que não existem mais no registro são ignorados; ids novos do
    registro que a preferência salva não conhece (ex.: card adicionado
    numa atualização) entram no final, na ordem de fábrica."""

    if not ordem_salva:
        return list(registro)

    indice = {item["id"]: item for item in registro}
    ordenado = [indice[i] for i in ordem_salva if i in indice]
    restantes = [item for item in registro if item["id"] not in ordem_salva]

    return ordenado + restantes


def _buscar_dados_dashboard():
    """Roda na worker thread (ver services/worker.py) -- as 7 chamadas
    de rede que Dashboard.carregar() precisa, incluindo os fallbacks
    silenciosos ja existentes (contas_pagar/clientes/movimentos_fiado
    nao devem travar o painel inteiro se falharem sozinhos)."""

    usuario = me()
    dados = dashboard()
    vendas = listar_vendas()
    produtos = listar_produtos()

    try:
        contas_pagar = listar_contas_pagar()
    except Exception:
        contas_pagar = []

    try:
        clientes = listar_clientes()
    except Exception:
        clientes = []

    try:
        movimentos_fiado = listar_movimentos()
    except Exception:
        movimentos_fiado = []

    usuarios_por_id = {}
    if usuario.get("admin"):
        try:
            usuarios_por_id = {u["id"]: u.get("nome") for u in listar_usuarios()}
        except Exception:
            usuarios_por_id = {}

    return (
        usuario, dados, vendas, produtos, contas_pagar,
        clientes, movimentos_fiado, usuarios_por_id,
    )


class Dashboard(QWidget):

    navegar_pdv = Signal()
    navegar_estoque = Signal()
    navegar_caixa = Signal()
    navegar_relatorios = Signal()

    def __init__(self, usuario_id=None):

        super().__init__()

        self._carregando = False

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        # cache dos ultimos dados carregados -- trocar de aba/periodo no
        # grafico ou nos combos de Formas de Pagamento/Top Produtos não
        # precisa buscar tudo de novo na API, só reprocessar o que já
        # está em memória
        self._vendas_finalizadas = []
        self._produtos_por_id = {}
        self._clientes = []
        self._totais_por_dia = {}
        self._lucros_por_dia = {}

        self._grafico_metrica = "vendas"
        self._grafico_periodo_dias = 7

        layout_externo = QVBoxLayout(self)
        layout_externo.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        conteudo = QWidget()
        conteudo.setStyleSheet("background:transparent;")

        self.layout_principal = QVBoxLayout(conteudo)
        self.layout_principal.setContentsMargins(28, 24, 28, 28)
        self.layout_principal.setSpacing(20)

        scroll.setWidget(conteudo)
        layout_externo.addWidget(scroll)

        # ======================
        # SAUDAÇÃO
        # ======================

        # usuario_id normalmente ja' vem pronto de quem construiu (ver
        # telas/principal.py, que ja' buscou isso pro Header/Sidebar) --
        # so' busca sozinho (sincrono) se for construido isolado, ex.
        # nos scripts de teste/demo
        self._usuario_id = usuario_id
        if self._usuario_id is None:
            self._usuario_id = (me() or {}).get("id")

        linha_saudacao = QHBoxLayout()
        linha_saudacao.setSpacing(12)

        col_saudacao = QVBoxLayout()
        col_saudacao.setSpacing(2)

        self.lbl_saudacao = QLabel()
        self.lbl_saudacao.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XXL}px; font-weight:800;
        """)
        col_saudacao.addWidget(self.lbl_saudacao)

        self.lbl_subtitulo_data = QLabel()
        self.lbl_subtitulo_data.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        col_saudacao.addWidget(self.lbl_subtitulo_data)

        linha_saudacao.addLayout(col_saudacao, stretch=1)

        self.badge_data = self._construir_badge_info("calendar")
        self.badge_atualizacao = self._construir_badge_info("refresh-cw")

        linha_saudacao.addWidget(self.badge_data, 0, Qt.AlignVCenter)
        linha_saudacao.addWidget(self.badge_atualizacao, 0, Qt.AlignVCenter)

        bt_personalizar = BotaoSecundario("Personalizar", "settings")
        bt_personalizar.setFixedWidth(160)
        bt_personalizar.clicked.connect(self.abrir_personalizar)
        linha_saudacao.addWidget(bt_personalizar, 0, Qt.AlignVCenter)

        self.layout_principal.addLayout(linha_saudacao)

        # ======================
        # ATALHOS
        # ======================

        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(16)

        self.card_pdv = NavCard(
            "Frente de Caixa", "Venda rápida",
            tokens.PRIMARIA, tokens.PRIMARIA_ESCURA, icone_nome="shopping-cart",
            atalho="F3", texto_botao="Abrir PDV",
        )
        self.card_estoque = NavCard(
            "Estoque", "Gestão de itens",
            tokens.SECUNDARIA, tokens.SECUNDARIA_ESCURA, icone_nome="package",
            texto_botao="Ver estoque",
        )
        self.card_caixa = NavCard(
            "Caixa", "Abertura e fechamento",
            tokens.ALERTA, tokens.ALERTA_ESCURA, icone_nome="wallet",
            texto_botao="Acessar caixa",
        )

        self.card_pdv.clicado.connect(self.navegar_pdv.emit)
        self.card_estoque.clicado.connect(self.navegar_estoque.emit)
        self.card_caixa.clicado.connect(self.navegar_caixa.emit)

        nav_layout.addWidget(self.card_pdv)
        nav_layout.addWidget(self.card_estoque)
        nav_layout.addWidget(self.card_caixa)

        self.layout_principal.addLayout(nav_layout)

        # ======================
        # AÇÕES RÁPIDAS
        # ======================

        self.layout_principal.addWidget(self._construir_acoes_rapidas())

        # ======================
        # KPIs
        # ======================

        self.grid_kpi = QGridLayout()
        self.grid_kpi.setSpacing(16)

        for coluna in range(4):
            self.grid_kpi.setColumnStretch(coluna, 1)

        self.kpi_faturamento = CardKPI(
            "Faturamento Hoje", "dollar-sign", tokens.PRIMARIA, destaque=True
        )
        self.kpi_lucro = CardKPI("Lucro Hoje", "trending-up", tokens.SECUNDARIA)
        self.kpi_ticket = CardKPI("Ticket Médio", "shopping-cart", tokens.PRIMARIA)
        self.kpi_pedidos = CardKPI("Pedidos Hoje", "file-text", tokens.PRIMARIA)
        self.kpi_caixa = CardKPI("Fluxo de Caixa", "wallet", tokens.SECUNDARIA)
        self.kpi_clientes = CardKPI("Clientes", "users", tokens.PRIMARIA)
        self.kpi_produtos = CardKPI("Produtos", "package", tokens.PRIMARIA)
        self.kpi_estoque = CardKPI("Estoque em Alerta", "alert-triangle", tokens.ALERTA)

        # Registro dos KPIs — fonte única de verdade pra ordem/visibilidade
        # personalizável (ver dashboard_personalizar.py). A ordem aqui é a
        # ordem padrão de fábrica, usada quando o usuário nunca personalizou.
        self.registro_kpis = [
            {"id": "faturamento", "titulo": "Faturamento Hoje", "widget": self.kpi_faturamento},
            {"id": "lucro", "titulo": "Lucro Hoje", "widget": self.kpi_lucro},
            {"id": "ticket", "titulo": "Ticket Médio", "widget": self.kpi_ticket},
            {"id": "pedidos", "titulo": "Pedidos Hoje", "widget": self.kpi_pedidos},
            {"id": "caixa", "titulo": "Fluxo de Caixa", "widget": self.kpi_caixa},
            {"id": "clientes", "titulo": "Clientes", "widget": self.kpi_clientes},
            {"id": "produtos", "titulo": "Produtos", "widget": self.kpi_produtos},
            {"id": "estoque", "titulo": "Estoque em Alerta", "widget": self.kpi_estoque},
        ]

        self.layout_principal.addLayout(self.grid_kpi)

        # ======================
        # GRÁFICO + FORMAS DE PAGAMENTO
        # ======================

        self.linha_graficos = QHBoxLayout()
        self.linha_graficos.setSpacing(16)

        self.secao_grafico = self._construir_secao_grafico()

        self.combo_periodo_pagamento = self._construir_combo_periodo(
            self._atualizar_formas_pagamento
        )
        self.secao_pagamentos = SecaoCard(
            "Formas de Pagamento", "credit-card",
            widget_acao=self.combo_periodo_pagamento,
        )
        self.secao_pagamentos.setMinimumWidth(280)

        self.layout_principal.addLayout(self.linha_graficos)

        # ======================
        # TOP PRODUTOS + VENDAS RECENTES + CLIENTES RECENTES + ALERTAS
        # ======================

        self.linha_listas = QHBoxLayout()
        self.linha_listas.setSpacing(16)

        self.combo_periodo_produtos = self._construir_combo_periodo(
            self._atualizar_top_produtos, padrao="30 dias",
        )
        self.secao_top_produtos = SecaoCard(
            "Top Produtos", "package",
            widget_acao=self.combo_periodo_produtos,
        )

        bt_ver_todas_vendas = QPushButton("Ver todas  →")
        bt_ver_todas_vendas.setCursor(Qt.PointingHandCursor)
        bt_ver_todas_vendas.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.PRIMARIA}; font-size:{tokens.TAMANHO_XS}px;
                font-weight:700;
            }}
            QPushButton:hover {{ color:{tokens.PRIMARIA_HOVER}; }}
        """)
        bt_ver_todas_vendas.clicked.connect(self.navegar_relatorios.emit)
        self.secao_vendas_recentes = SecaoCard(
            "Vendas Recentes", "shopping-cart",
            widget_acao=bt_ver_todas_vendas,
        )

        self.secao_clientes_recentes = SecaoCard("Clientes Recentes", "users")
        self.secao_alertas = SecaoCard("Alertas", "alert-triangle")

        self.layout_principal.addLayout(self.linha_listas)

        # Registro dos painéis — mesmo espírito do registro de KPIs, mas
        # só com mostrar/ocultar (a proporção 6:4 do gráfico+pagamentos e
        # o trio igual de baixo têm um acoplamento visual que reordenar
        # livremente quebraria; ver decisão registrada no plano da Fase 1).
        self.registro_paineis = [
            {"id": "grafico", "titulo": "Vendas — últimos 7 dias", "widget": self.secao_grafico, "linha": "graficos", "peso": 6},
            {"id": "pagamentos", "titulo": "Formas de Pagamento", "widget": self.secao_pagamentos, "linha": "graficos", "peso": 4},
            {"id": "top_produtos", "titulo": "Top Produtos", "widget": self.secao_top_produtos, "linha": "listas", "peso": 1},
            {"id": "vendas_recentes", "titulo": "Vendas Recentes", "widget": self.secao_vendas_recentes, "linha": "listas", "peso": 1},
            {"id": "clientes_recentes", "titulo": "Clientes Recentes", "widget": self.secao_clientes_recentes, "linha": "listas", "peso": 1},
            {"id": "alertas", "titulo": "Alertas", "widget": self.secao_alertas, "linha": "listas", "peso": 1},
        ]

        self.layout_principal.addStretch()

        self._aplicar_layout_kpis()
        self._aplicar_layout_paineis()

        self.carregar()

    # ======================================
    # CABEÇALHO
    # ======================================

    def _construir_badge_info(self, icone_nome):

        badge = QFrame()
        badge.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

        layout = QHBoxLayout(badge)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(6)

        lbl_icone = QLabel()
        lbl_icone.setPixmap(icone_pixmap(icone_nome, cor=tokens.TEXTO_TERCIARIO, tamanho=14))
        lbl_icone.setStyleSheet("background:transparent;")

        lbl_texto = QLabel()
        lbl_texto.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:600;
        """)

        layout.addWidget(lbl_icone)
        layout.addWidget(lbl_texto)

        # guarda a referencia direta no proprio QFrame -- mais simples
        # que objectName + findChild pra um widget tão pequeno
        badge.lbl_texto = lbl_texto

        return badge

    def _construir_acoes_rapidas(self):

        card = Card()

        layout = QHBoxLayout(card)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)

        lbl_titulo = QLabel("Ações rápidas")
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)
        layout.addWidget(lbl_titulo)

        acoes = [
            ("shopping-cart", "Nova venda", "F3", self.navegar_pdv.emit),
            ("package", "Novo produto", "F4", self._acao_novo_produto),
            ("users", "Novo cliente", "F7", self._acao_novo_cliente),
            ("file-text", "Registrar despesa", "F8", self._acao_registrar_despesa),
        ]

        for icone_nome, texto, atalho, callback in acoes:
            botao = BotaoSecundario(texto, icone_nome=icone_nome)
            botao.setToolTip(f"Atalho: {atalho}")
            botao.clicked.connect(callback)
            layout.addWidget(botao)

        layout.addStretch()

        # atalhos F4/F7/F8 -- F3 (nova venda) já é global, tratado em
        # telas/principal.py. Escopo por widget (nao global) pra nao
        # brigar com os F2/F4/F6 que o PDV ja usa pra outras coisas --
        # cada um só dispara quando a tela dona do atalho está visível.
        self._atalho_novo_produto = QShortcut(QKeySequence("F4"), self)
        self._atalho_novo_produto.activated.connect(self._acao_novo_produto)

        self._atalho_novo_cliente = QShortcut(QKeySequence("F7"), self)
        self._atalho_novo_cliente.activated.connect(self._acao_novo_cliente)

        self._atalho_registrar_despesa = QShortcut(QKeySequence("F8"), self)
        self._atalho_registrar_despesa.activated.connect(self._acao_registrar_despesa)

        return card

    def _acao_novo_produto(self):

        from telas.cadastro_produto import CadastroProdutoWindow

        dialogo = CadastroProdutoWindow()
        dialogo.exec()

    def _acao_novo_cliente(self):

        from telas.cadastro_cliente import CadastroClienteDialog

        dialogo = CadastroClienteDialog(parent=self)
        dialogo.exec()

    def _acao_registrar_despesa(self):

        from telas.cadastro_despesa import CadastroDespesaDialog

        dialogo = CadastroDespesaDialog(parent=self)
        dialogo.exec()

    # ======================================
    # PERSONALIZAÇÃO
    # ======================================

    def _preferencia_kpis(self):
        salvo = preferencias_service.carregar(self._usuario_id, "dashboard_kpis", {})
        return salvo.get("ordem", []), set(salvo.get("ocultos", []))

    def _preferencia_paineis_ocultos(self):
        salvo = preferencias_service.carregar(self._usuario_id, "dashboard_paineis", {})
        return set(salvo.get("ocultos", []))

    def _aplicar_layout_kpis(self):

        while self.grid_kpi.count():
            self.grid_kpi.takeAt(0)

        ordem_salva, ocultos = self._preferencia_kpis()
        ordenado = _reordenar_por_preferencia(self.registro_kpis, ordem_salva)
        visiveis = [c for c in ordenado if c["id"] not in ocultos]

        for i, card in enumerate(visiveis):
            self.grid_kpi.addWidget(card["widget"], i // 4, i % 4)

        self._animar_kpis_escalonado(visiveis)

    def _animar_kpis_escalonado(self, cards):
        """Entrada em leque, um card de cada vez -- roda tanto no
        carregamento inicial quanto depois de reordenar/mostrar-ocultar
        pela Personalização, reforçando visualmente que o grid mudou.
        Só fade (sem slide_up): esses cards vivem num QGridLayout
        dentro de uma QScrollArea, e mover widgets manualmente nesse
        combo briga com o sistema de layout (confirmado -- ver captura
        offscreen corrompida ao testar com slide_up aqui)."""

        for indice, card in enumerate(cards):
            widget = card["widget"]
            atraso = 40 * indice
            QTimer.singleShot(
                atraso,
                lambda widget=widget: fade_in(widget, duracao=260),
            )

    def _aplicar_layout_paineis(self):

        while self.linha_graficos.count():
            self.linha_graficos.takeAt(0)

        while self.linha_listas.count():
            self.linha_listas.takeAt(0)

        ocultos = self._preferencia_paineis_ocultos()

        for painel in self.registro_paineis:

            if painel["id"] in ocultos:
                continue

            linha = self.linha_graficos if painel["linha"] == "graficos" else self.linha_listas
            linha.addWidget(painel["widget"], stretch=painel["peso"])

    def abrir_personalizar(self):

        from telas.dashboard_personalizar import PersonalizarDashboardDialog

        dialogo = PersonalizarDashboardDialog(
            self._usuario_id,
            self.registro_kpis,
            self.registro_paineis,
            parent=self,
        )

        if dialogo.exec():
            self._aplicar_layout_kpis()
            self._aplicar_layout_paineis()

    # ======================================
    # GRÁFICO — ABAS DE MÉTRICA/PERÍODO
    # ======================================

    def _construir_secao_grafico(self):

        secao = SecaoCard("Desempenho de vendas", "bar-chart-2")

        subtitulo = QLabel("Acompanhe o desempenho da sua loja")
        subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)
        secao.corpo.addWidget(subtitulo)

        barra_abas = QHBoxLayout()
        barra_abas.setSpacing(16)

        grupo_metrica_layout = QHBoxLayout()
        grupo_metrica_layout.setSpacing(2)

        self.bt_aba_vendas = self._botao_aba("Vendas")
        self.bt_aba_lucro = self._botao_aba("Lucro")
        self.bt_aba_vendas.setChecked(True)

        self._grupo_metrica = QButtonGroup(self)
        self._grupo_metrica.setExclusive(True)
        self._grupo_metrica.addButton(self.bt_aba_vendas)
        self._grupo_metrica.addButton(self.bt_aba_lucro)

        self.bt_aba_vendas.clicked.connect(lambda: self._definir_metrica_grafico("vendas"))
        self.bt_aba_lucro.clicked.connect(lambda: self._definir_metrica_grafico("lucro"))

        grupo_metrica_layout.addWidget(self.bt_aba_vendas)
        grupo_metrica_layout.addWidget(self.bt_aba_lucro)

        grupo_periodo_layout = QHBoxLayout()
        grupo_periodo_layout.setSpacing(2)

        self.bt_periodo_7 = self._botao_aba("7 dias")
        self.bt_periodo_30 = self._botao_aba("30 dias")
        self.bt_periodo_90 = self._botao_aba("3 meses")
        self.bt_periodo_7.setChecked(True)

        self._grupo_periodo = QButtonGroup(self)
        self._grupo_periodo.setExclusive(True)

        for botao, dias in (
            (self.bt_periodo_7, 7), (self.bt_periodo_30, 30), (self.bt_periodo_90, 90),
        ):
            self._grupo_periodo.addButton(botao)
            botao.clicked.connect(lambda _checked=False, d=dias: self._definir_periodo_grafico(d))
            grupo_periodo_layout.addWidget(botao)

        barra_abas.addLayout(grupo_metrica_layout)
        barra_abas.addStretch()
        barra_abas.addLayout(grupo_periodo_layout)

        secao.corpo.addLayout(barra_abas)

        self.grafico = GraficoArea()
        secao.corpo.addWidget(self.grafico)

        return secao

    def _botao_aba(self, texto):

        botao = QPushButton(texto)
        botao.setCheckable(True)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setFixedHeight(30)
        botao.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: {tokens.RADIUS_SM}px;
                color: {tokens.TEXTO_SECUNDARIO};
                font-size: {tokens.TAMANHO_SM}px;
                font-weight: 600;
                padding: 0 14px;
            }}
            QPushButton:checked {{
                background: {tokens.PRIMARIA};
                color: {tokens.TEXTO_CLARO};
            }}
            QPushButton:hover:!checked {{
                background: {tokens.FUNDO};
            }}
        """)

        return botao

    def _definir_metrica_grafico(self, metrica):
        self._grafico_metrica = metrica
        self._atualizar_grafico()

    def _definir_periodo_grafico(self, dias):
        self._grafico_periodo_dias = dias
        self._atualizar_grafico()

    def _construir_combo_periodo(self, ao_mudar, padrao="Hoje"):

        combo = QComboBox()
        combo.addItems([rotulo for rotulo, _dias in OPCOES_PERIODO])
        combo.setCurrentText(padrao)
        combo.setCursor(Qt.PointingHandCursor)
        combo.setStyleSheet(f"""
            QComboBox {{
                border: 1px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 3px 10px; background: {tokens.CARD}; color: {tokens.TEXTO_SECUNDARIO};
                font-size: {tokens.TAMANHO_XS}px;
            }}
        """)
        combo.currentTextChanged.connect(lambda _texto: ao_mudar())

        return combo

    # ======================================
    # CARREGAMENTO DE DADOS
    # ======================================

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True

        self.combo_periodo_pagamento.setEnabled(False)
        self.combo_periodo_produtos.setEnabled(False)

        agora = datetime.now()
        dia_semana = DIAS_SEMANA_COMPLETO[agora.weekday()]
        data_extenso = f"{agora.day} de {MESES_COMPLETO[agora.month - 1]} de {agora.year}"

        self.lbl_subtitulo_data.setText(
            f"Aqui está o resumo da sua loja para hoje, {data_extenso}."
        )
        self.badge_data.lbl_texto.setText(f"{dia_semana}, {agora.strftime('%d/%m/%Y')}")

        rodar_em_thread(
            self,
            _buscar_dados_dashboard,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _ao_carregar_sucesso(self, resultado):
        try:
            (
                usuario, dados, vendas, produtos, contas_pagar,
                clientes, movimentos_fiado, usuarios_por_id,
            ) = resultado

            nome_usuario = usuario.get("nome") or "Usuário"
            self.lbl_saudacao.setText(f"Olá, {nome_usuario}!")

            agora = datetime.now()
            self.badge_atualizacao.lbl_texto.setText(
                f"Atualizado às {agora.strftime('%H:%M')}"
            )

            produtos_por_id = {p["id"]: p for p in produtos}
            vendas_finalizadas = [v for v in vendas if v.get("status") == "FINALIZADA"]

            # cache pra trocas de aba/periodo (grafico, formas de
            # pagamento, top produtos) reprocessarem sem bater na API
            # de novo
            self._vendas_finalizadas = vendas_finalizadas
            self._produtos_por_id = produtos_por_id
            self._clientes = clientes
            self._totais_por_dia, self._lucros_por_dia = self._construir_series_diarias(
                vendas_finalizadas, produtos_por_id
            )

            self._atualizar_kpis(dados)
            self._atualizar_grafico()
            self._atualizar_formas_pagamento()
            self._atualizar_top_produtos()
            self._atualizar_vendas_recentes(vendas_finalizadas, usuarios_por_id)
            self._atualizar_clientes_recentes(vendas_finalizadas, clientes)
            self._atualizar_alertas(produtos, contas_pagar, clientes, movimentos_fiado)
        except Exception as erro:
            self._ao_carregar_erro(erro)

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self,
            "Erro",
            f"Não foi possível carregar o painel.\n{erro}",
        )

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self.combo_periodo_pagamento.setEnabled(True)
        self.combo_periodo_produtos.setEnabled(True)

    def _construir_series_diarias(self, vendas_finalizadas, produtos_por_id):
        """Soma faturamento e lucro por dia, uma vez só -- reaproveitado
        tanto pelos KPIs (hoje vs. ontem) quanto pelo gráfico (que pode
        pedir 7/30/90 dias pra trás sem precisar refiltrar a lista
        inteira de vendas a cada troca de aba)."""

        totais_por_dia = {}
        lucros_por_dia = {}

        for venda in vendas_finalizadas:

            data_venda = _parse_data(venda.get("data"))

            if data_venda is None:
                continue

            dia = data_venda.date()

            totais_por_dia[dia] = totais_por_dia.get(dia, 0.0) + float(venda.get("valor_total", 0))

            lucro_venda = 0.0

            for item in venda.get("itens", []):
                produto = produtos_por_id.get(item.get("produto_id"))
                custo = float(produto.get("preco_custo", 0)) if produto else 0.0
                valor_unit = float(item.get("valor_unitario", 0))
                lucro_venda += (valor_unit - custo) * item.get("quantidade", 0)

            lucros_por_dia[dia] = lucros_por_dia.get(dia, 0.0) + lucro_venda

        return totais_por_dia, lucros_por_dia

    def _atualizar_kpis(self, dados):

        hoje = datetime.now().date()
        ontem = hoje - timedelta(days=1)

        vendas_hoje = float(dados.get("vendas_hoje", 0) or 0)
        vendas_hoje_qtd = int(dados.get("vendas_hoje_qtd", 0) or 0)
        vendas_ontem = self._totais_por_dia.get(ontem, 0.0)
        vendas_ontem_qtd = sum(
            1 for v in self._vendas_finalizadas
            if (_parse_data(v.get("data")) or datetime.min).date() == ontem
        )

        self.kpi_faturamento.definir_valor(formatar_moeda(vendas_hoje))
        self.kpi_faturamento.definir_variacao(_variacao_percentual(vendas_hoje, vendas_ontem))

        self.kpi_pedidos.definir_valor(str(vendas_hoje_qtd))
        self.kpi_pedidos.definir_variacao(_variacao_percentual(vendas_hoje_qtd, vendas_ontem_qtd))

        ticket_medio = (vendas_hoje / vendas_hoje_qtd) if vendas_hoje_qtd else 0
        ticket_medio_ontem = (vendas_ontem / vendas_ontem_qtd) if vendas_ontem_qtd else 0
        self.kpi_ticket.definir_valor(formatar_moeda(ticket_medio))
        self.kpi_ticket.definir_variacao(_variacao_percentual(ticket_medio, ticket_medio_ontem))

        # sem selo de variação: saldo/contagens são um "retrato agora",
        # não um fluxo diário -- comparar com "ontem" não tem o mesmo
        # significado e não temos snapshot histórico salvo pra isso
        self.kpi_caixa.definir_valor(formatar_moeda(dados.get("saldo_caixa", 0) or 0))
        self.kpi_clientes.definir_valor(str(dados.get("clientes", 0)))
        self.kpi_produtos.definir_valor(str(dados.get("produtos", 0)))
        self.kpi_estoque.definir_valor(str(dados.get("estoque_baixo", 0)))

        lucro_hoje = self._lucros_por_dia.get(hoje, 0.0)
        lucro_ontem = self._lucros_por_dia.get(ontem, 0.0)
        self.kpi_lucro.definir_valor(formatar_moeda(lucro_hoje))
        self.kpi_lucro.definir_variacao(_variacao_percentual(lucro_hoje, lucro_ontem))

    def _atualizar_grafico(self):

        hoje = datetime.now().date()
        dias = self._grafico_periodo_dias
        serie = self._totais_por_dia if self._grafico_metrica == "vendas" else self._lucros_por_dia

        rotulos = []
        rotulos_completos = []
        valores = []

        if dias <= 30:

            for i in range(dias - 1, -1, -1):

                dia = hoje - timedelta(days=i)
                valores.append(serie.get(dia, 0.0))

                if dias <= 7:
                    rotulos.append(DIAS_SEMANA_ABREV[dia.weekday()])
                else:
                    rotulos.append(dia.strftime("%d/%m"))

                rotulos_completos.append(
                    f"{DIAS_SEMANA_COMPLETO[dia.weekday()]}, {dia.strftime('%d/%m')}"
                )

        else:

            # 3 meses fica denso demais em dias -- agrupa por semana
            num_semanas = dias // 7

            for i in range(num_semanas - 1, -1, -1):

                fim_semana = hoje - timedelta(days=i * 7)
                inicio_semana = fim_semana - timedelta(days=6)

                total_semana = sum(
                    valor for dia_serie, valor in serie.items()
                    if inicio_semana <= dia_serie <= fim_semana
                )

                valores.append(total_semana)
                rotulos.append(inicio_semana.strftime("%d/%m"))
                rotulos_completos.append(
                    f"Semana de {inicio_semana.strftime('%d/%m')} a {fim_semana.strftime('%d/%m')}"
                )

        self.grafico.definir_dados(rotulos, valores, rotulos_completos)

    def _atualizar_formas_pagamento(self):

        vendas_periodo = self._filtrar_por_periodo(self.combo_periodo_pagamento.currentText())

        totais_forma = {}

        for venda in vendas_periodo:
            forma = venda.get("forma_pagamento", "DINHEIRO")
            totais_forma[forma] = totais_forma.get(forma, 0) + float(venda.get("valor_total", 0))

        self.secao_pagamentos.limpar_corpo()

        if not totais_forma:
            self.secao_pagamentos.adicionar_vazio("Nenhuma venda registrada no período.")
            return

        maior = max(totais_forma.values())

        for forma, valor in sorted(totais_forma.items(), key=lambda item: -item[1]):

            percentual = (valor / maior * 100) if maior else 0

            linha = LinhaProgresso(
                NOMES_FORMA_PAGAMENTO.get(forma, forma),
                None,
                formatar_moeda(valor),
                percentual,
                CORES_FORMA_PAGAMENTO.get(forma, tokens.PRIMARIA),
            )
            self.secao_pagamentos.corpo.addWidget(linha)

    def _filtrar_por_periodo(self, rotulo_periodo):

        dias = dict(OPCOES_PERIODO).get(rotulo_periodo, 30)
        hoje = datetime.now().date()
        limite = hoje - timedelta(days=dias - 1)

        return [
            v for v in self._vendas_finalizadas
            if (_parse_data(v.get("data")) or datetime.min).date() >= limite
        ]

    def _atualizar_top_produtos(self):

        vendas_periodo = self._filtrar_por_periodo(self.combo_periodo_produtos.currentText())

        qtd_por_produto = {}

        for venda in vendas_periodo:
            for item in venda.get("itens", []):
                pid = item.get("produto_id")
                qtd_por_produto[pid] = qtd_por_produto.get(pid, 0) + item.get("quantidade", 0)

        self.secao_top_produtos.limpar_corpo()

        top_produtos = sorted(qtd_por_produto.items(), key=lambda item: -item[1])[:5]

        if not top_produtos:
            self.secao_top_produtos.adicionar_vazio("Sem vendas no período.")
            return

        maior_qtd = top_produtos[0][1]

        for posicao, (pid, qtd) in enumerate(top_produtos, start=1):

            produto = self._produtos_por_id.get(pid)
            nome = produto.get("nome") if produto else f"Produto #{pid}"
            percentual = (qtd / maior_qtd * 100) if maior_qtd else 0

            linha = LinhaProgresso(
                nome,
                "unidades vendidas no período",
                f"{qtd} un.",
                percentual,
                tokens.PRIMARIA,
            )

            self.secao_top_produtos.corpo.addWidget(self._linha_com_ranking(posicao, linha))

    def _linha_com_ranking(self, posicao, widget):

        linha = QFrame()
        linha.setStyleSheet("background:transparent; border:none;")

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        cores_pos = {1: tokens.ALERTA, 2: tokens.TEXTO_TERCIARIO, 3: tokens.ALERTA_TEXTO}
        cor_numero = cores_pos.get(posicao, tokens.TEXTO_TERCIARIO)

        selo = QLabel(str(posicao))
        selo.setFixedSize(22, 22)
        selo.setAlignment(Qt.AlignCenter)
        selo.setStyleSheet(f"""
            background: {tokens.FUNDO}; color: {cor_numero};
            border-radius: 11px; font-size: 11px; font-weight: 800;
        """)

        layout.addWidget(selo, 0, Qt.AlignTop)
        layout.addWidget(widget, stretch=1)

        return linha

    def _atualizar_vendas_recentes(self, vendas_finalizadas, usuarios_por_id=None):

        self.secao_vendas_recentes.limpar_corpo()

        recentes = sorted(
            vendas_finalizadas,
            key=lambda v: v.get("data") or "",
            reverse=True,
        )[:6]

        if not recentes:
            self.secao_vendas_recentes.adicionar_vazio("Nenhuma venda registrada ainda.")
            return

        self.secao_vendas_recentes.corpo.addWidget(self._cabecalho_tabela_vendas())

        for venda in recentes:
            data_venda = _parse_data(venda.get("data"))
            hora_texto = data_venda.strftime("%H:%M") if data_venda else "—"
            self.secao_vendas_recentes.corpo.addWidget(
                self._linha_venda_recente(venda, hora_texto)
            )

    def _cabecalho_tabela_vendas(self):

        linha = QFrame()
        linha.setStyleSheet("background:transparent; border:none;")

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(10)

        for texto, peso in (("Hora", 0), ("Produto", 1), ("Pagamento", 0)):
            lbl = QLabel(texto)
            lbl.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_XS}px; font-weight:700;
            """)
            layout.addWidget(lbl, stretch=peso)

        return linha

    def _linha_venda_recente(self, venda, hora_texto):

        linha = QFrame()
        linha.setStyleSheet("background:transparent; border:none;")

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        lbl_hora = QLabel(hora_texto)
        lbl_hora.setFixedWidth(40)
        lbl_hora.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        itens = venda.get("itens", [])
        primeiro = self._produtos_por_id.get(itens[0].get("produto_id")) if itens else None
        nome_produto = primeiro.get("nome") if primeiro else "Venda"
        if len(itens) > 1:
            nome_produto = f"{nome_produto} +{len(itens) - 1}"

        lbl_produto = QLabel(nome_produto)
        lbl_produto.setWordWrap(True)
        lbl_produto.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)

        forma = venda.get("forma_pagamento", "")
        badge_forma = Badge(
            NOMES_FORMA_PAGAMENTO.get(forma, forma),
            VARIANTE_BADGE_FORMA.get(forma, "neutro"),
        )

        layout.addWidget(lbl_hora)
        layout.addWidget(lbl_produto, stretch=1)
        layout.addWidget(badge_forma)

        return linha

    def _atualizar_clientes_recentes(self, vendas_finalizadas, clientes):

        self.secao_clientes_recentes.limpar_corpo()

        nomes_por_id = {c["id"]: c.get("nome") for c in clientes}

        ultima_compra_por_cliente = {}

        for venda in vendas_finalizadas:

            cliente_id = venda.get("cliente_id")

            if cliente_id is None or cliente_id not in nomes_por_id:
                continue

            data_venda = _parse_data(venda.get("data"))

            if data_venda is None:
                continue

            atual = ultima_compra_por_cliente.get(cliente_id)

            if atual is None or data_venda > atual:
                ultima_compra_por_cliente[cliente_id] = data_venda

        recentes = sorted(
            ultima_compra_por_cliente.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:6]

        if not recentes:
            self.secao_clientes_recentes.adicionar_vazio(
                "Nenhuma compra de cliente identificado ainda."
            )
            return

        for cliente_id, data_compra in recentes:
            nome = nomes_por_id.get(cliente_id, f"Cliente #{cliente_id}")
            self.secao_clientes_recentes.corpo.addWidget(
                self._linha_cliente_recente(nome, data_compra)
            )

    def _linha_cliente_recente(self, nome, data_compra):

        linha = QFrame()
        linha.setStyleSheet("background:transparent; border:none;")

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        iniciais = "".join(parte[0] for parte in nome.split()[:2]).upper() or "?"

        avatar = QLabel(iniciais)
        avatar.setFixedSize(30, 30)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet(f"""
            background: {tokens.PRIMARIA_CLARA}; color: {tokens.PRIMARIA};
            border-radius: 15px; font-size: 11px; font-weight: 700;
        """)

        lbl_nome = QLabel(nome)
        lbl_nome.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)

        hoje = datetime.now().date()

        if data_compra.date() == hoje:
            texto_data = f"Hoje {data_compra.strftime('%H:%M')}"
        elif data_compra.date() == hoje - timedelta(days=1):
            texto_data = f"Ontem {data_compra.strftime('%H:%M')}"
        else:
            texto_data = data_compra.strftime("%d/%m")

        lbl_data = QLabel(texto_data)
        lbl_data.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        layout.addWidget(avatar)
        layout.addWidget(lbl_nome, stretch=1)
        layout.addWidget(lbl_data)

        return linha

    def _atualizar_alertas(self, produtos, contas_pagar, clientes, movimentos_fiado):

        self.secao_alertas.limpar_corpo()

        hoje = datetime.now().date()

        criticos = [
            p for p in produtos
            if p.get("ativo", True) and p.get("estoque", 0) <= p.get("estoque_minimo", 0)
        ][:2]

        pendentes = sorted(
            [c for c in contas_pagar if c.get("status") == "PENDENTE"],
            key=lambda c: c.get("data_vencimento") or "",
        )[:2]

        inadimplentes = self._clientes_inadimplentes(clientes, movimentos_fiado)[:2]
        aniversariantes = self._clientes_aniversariantes(clientes)[:2]

        if not (criticos or pendentes or inadimplentes or aniversariantes):
            self.secao_alertas.adicionar_vazio("Nenhum alerta no momento. Tudo em ordem!")
            return

        for produto in criticos:

            self.secao_alertas.corpo.addWidget(
                self._linha_alerta(
                    f"Estoque baixo: {produto.get('nome')}",
                    f"{produto.get('estoque')} un. (mínimo {produto.get('estoque_minimo')})",
                    "erro" if produto.get("estoque", 0) == 0 else "alerta",
                )
            )

        for conta in pendentes:

            vencimento = _parse_data(conta.get("data_vencimento"))
            dias = (vencimento.date() - hoje).days if vencimento else None

            if dias is None:
                texto_prazo = "sem data de vencimento"
            elif dias < 0:
                texto_prazo = f"vencida há {abs(dias)} dia(s)"
            elif dias == 0:
                texto_prazo = "vence hoje"
            else:
                texto_prazo = f"vence em {dias} dia(s)"

            self.secao_alertas.corpo.addWidget(
                self._linha_alerta(
                    conta.get("descricao") or "Conta a pagar",
                    f"{formatar_moeda(conta.get('valor', 0))} — {texto_prazo}",
                    "erro" if (dias is not None and dias < 0) else "alerta",
                )
            )

        for nome, saldo in inadimplentes:

            self.secao_alertas.corpo.addWidget(
                self._linha_alerta(
                    f"Cliente devendo: {nome}",
                    f"Saldo em aberto: {formatar_moeda(saldo)}",
                    "alerta",
                )
            )

        for nome in aniversariantes:

            self.secao_alertas.corpo.addWidget(
                self._linha_alerta(
                    f"Aniversário hoje: {nome}",
                    "Uma ligação ou mensagem de parabéns pode render uma venda.",
                    "alerta",
                )
            )

    def _clientes_inadimplentes(self, clientes, movimentos_fiado):
        """Agrega saldo por cliente client-side, com o mesmo sinal usado
        no backend (COMPRA soma, o resto — PAGAMENTO — subtrai; ver
        MovimentoFiadoRepository.saldo_por_cliente). Reaproveita o padrão
        já usado no ranking de produtos: nada de endpoint novo."""

        nomes_por_id = {c["id"]: c.get("nome") for c in clientes}

        saldo_por_cliente = {}

        for mov in movimentos_fiado:

            cliente_id = mov.get("cliente_id")
            valor = float(mov.get("valor", 0) or 0)
            sinal = 1 if mov.get("tipo") == "COMPRA" else -1

            saldo_por_cliente[cliente_id] = (
                saldo_por_cliente.get(cliente_id, 0) + sinal * valor
            )

        devedores = [
            (nomes_por_id.get(cid, f"Cliente #{cid}"), saldo)
            for cid, saldo in saldo_por_cliente.items()
            if saldo > 0.009 and cid in nomes_por_id
        ]

        return sorted(devedores, key=lambda item: -item[1])

    def _clientes_aniversariantes(self, clientes):
        """Depende de Cliente.data_nascimento — campo novo da Onda C.
        Enquanto o backend não expõe esse campo, a lista fica vazia sem
        gerar erro (nenhum cliente terá a chave, então o filtro abaixo
        simplesmente não encontra ninguém)."""

        hoje = datetime.now().date()
        nomes = []

        for cliente in clientes:

            nascimento = _parse_data(cliente.get("data_nascimento"))

            if nascimento is None:
                continue

            if (nascimento.month, nascimento.day) == (hoje.month, hoje.day):
                nomes.append(cliente.get("nome"))

        return nomes

    # ======================================
    # LINHAS AUXILIARES
    # ======================================

    def _linha_alerta(self, titulo, subtitulo, variante):

        linha = QFrame()
        linha.setStyleSheet("background:transparent; border:none;")

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        cor = tokens.ERRO if variante == "erro" else tokens.ALERTA

        marcador = QFrame()
        marcador.setFixedWidth(4)
        marcador.setStyleSheet(f"background:{cor}; border-radius:2px;")

        col_texto = QVBoxLayout()
        col_texto.setSpacing(1)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setWordWrap(True)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)

        lbl_sub = QLabel(subtitulo)
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_texto.addWidget(lbl_titulo)
        col_texto.addWidget(lbl_sub)

        layout.addWidget(marcador)
        layout.addLayout(col_texto, stretch=1)

        return linha
