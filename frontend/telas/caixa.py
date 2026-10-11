from datetime import datetime

from telas.suprimento import SuprimentoWindow
from telas.sangria import SangriaWindow
from telas.abrir_caixa import AbrirCaixaWindow
from telas.fechar_caixa import FecharCaixaWindow

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QDialog,
    QMessageBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from services.caixa_service import (
    caixa_aberto,
    abrir_caixa,
    resumo_caixa,
    listar_movimentos_caixa,
)

from services.movimento_caixa_service import (
    criar_sangria,
    criar_suprimento,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import Badge, BotaoSecundario, BotaoSucesso
from services.worker import rodar_em_thread, em_paralelo
from services import api
from utils.formatacao import formatar_moeda


_INFO_TIPO_MOVIMENTO = {
    "VENDA": ("Venda", "info"),
    "SUPRIMENTO": ("Suprimento", "sucesso"),
    "SANGRIA": ("Sangria", "erro"),
    "RECEBIMENTO_FIADO": ("Recebimento fiado", "sucesso"),
    "ESTORNO": ("Estorno", "alerta"),
}


def _formatar_data_movimento(texto):
    """"YYYY-MM-DDTHH:MM:SS" (ou variação com espaço) -> "dd/mm/yyyy
    HH:MM" -- mais rápido de ler numa lista comprida do que o ISO cru."""

    texto = str(texto or "")

    try:
        limpo = texto.replace("T", " ")[:16]
        dt = datetime.strptime(limpo, "%Y-%m-%d %H:%M")
        return dt.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return texto[:19]


def _texto_abertura(texto):
    """"Aberto hoje às 17:27" / "Aberto ontem às 22:10" / "Aberto em
    03/10 às 08:00" -- antes aparecia a data crua "2026-10-05 17:27"."""

    try:
        dt = datetime.fromisoformat(str(texto).replace("T", " ")[:19])
    except ValueError:
        return f"Aberto em {str(texto or '')[:16]}"

    hoje = datetime.now().date()
    hora = dt.strftime("%H:%M")
    if dt.date() == hoje:
        return f"Aberto hoje às {hora}"
    if (hoje - dt.date()).days == 1:
        return f"Aberto ontem às {hora}"
    return f"Aberto em {dt.strftime('%d/%m')} às {hora}"


def _cor_valor_movimento(tipo):
    if tipo in ("SUPRIMENTO", "VENDA", "RECEBIMENTO_FIADO"):
        return tokens.SECUNDARIA_HOVER
    if tipo in ("SANGRIA", "ESTORNO"):
        return tokens.ERRO
    return tokens.TEXTO


def _celula_valor_movimento(tipo, texto_valor):
    """QLabel colorido pro valor do movimento -- precisa ser um cell
    widget (não um QTableWidgetItem comum) porque o QSS da tabela
    ("QTableWidget::item { color: ... }") tem prioridade sobre
    setForeground(), então colorir o item direto não teria efeito."""

    container = QWidget()
    container.setStyleSheet("background:transparent;")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(12, 0, 12, 0)
    layout.setSpacing(0)

    lbl = QLabel(texto_valor)
    lbl.setStyleSheet(f"""
        background:transparent; color:{_cor_valor_movimento(tipo)};
        font-weight:700; font-size:{tokens.TAMANHO_BASE}px;
    """)
    layout.addWidget(lbl)
    layout.addStretch()

    return container


def _pill_tipo_movimento(tipo):
    """Etiqueta colorida (pill) pra cada tipo de movimento no histórico
    do caixa -- mesma linguagem visual das pills de tipo usadas na
    timeline da ficha do cliente."""

    rotulo, variante = _INFO_TIPO_MOVIMENTO.get(
        tipo, (tipo.replace("_", " ").title() if tipo else "—", "neutro")
    )

    fundo, cor_texto = Badge.variantes()[variante]

    container = QWidget()
    container.setStyleSheet("background:transparent;")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(10, 0, 0, 0)
    layout.setSpacing(0)

    pill = QLabel(rotulo)
    pill.setStyleSheet(f"""
        background:{fundo}; color:{cor_texto};
        border-radius:{tokens.RADIUS_PILL}px;
        font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        padding:3px 10px;
    """)
    # centralizada na vertical -- sem o alinhamento a etiqueta
    # esticava até a altura inteira da linha
    layout.addWidget(pill, 0, Qt.AlignVCenter)
    layout.addStretch()

    return container


def _buscar_dados_caixa():
    """Roda na worker thread -- caixa_aberto() + resumo_caixa() +
    listar_movimentos_caixa(), as 3 chamadas que Caixa.carregar()
    precisa. caixa_aberto() precisa vir primeiro (movimentos depende
    do id dele, e' o que decide se tem caixa aberto) -- as outras 2
    dependem so' desse resultado, nao uma da outra, entao disparam
    juntas."""
    caixa = caixa_aberto()

    if caixa is None:
        return caixa, None, []

    resumo, movimentos = em_paralelo(
        (resumo_caixa,), (listar_movimentos_caixa, caixa["id"])
    )

    return caixa, resumo or {}, movimentos


class Caixa(QWidget):

    def __init__(self):
        super().__init__()

        self._carregando = False

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self.paginas = QStackedWidget()
        raiz.addWidget(self.paginas)

        self.pagina_sem_caixa = self._criar_pagina_sem_caixa()
        self.pagina_com_caixa = self._criar_pagina_com_caixa()

        self.paginas.addWidget(self.pagina_sem_caixa)
        self.paginas.addWidget(self.pagina_com_caixa)

        self.carregar()

    # ======================================
    # PÁGINA · SEM CAIXA ABERTO
    # ======================================

    def _criar_pagina_sem_caixa(self):

        pagina = QWidget()

        layout = QVBoxLayout(pagina)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        icone = QLabel()
        icone.setAlignment(Qt.AlignCenter)
        icone.setFixedSize(72, 72)
        icone.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA};
            border-radius:36px;
        """)
        icone.setPixmap(icone_pixmap("lock", cor=tokens.PRIMARIA, tamanho=30))

        titulo = QLabel("Nenhum caixa aberto")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_XL}px; font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            "Abra o caixa para liberar o Frente de Caixa e "
            "começar a registrar vendas."
        )
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_SM}px; color:{tokens.TEXTO_SECUNDARIO};
        """)
        subtitulo.setFixedWidth(360)

        self.bt_abrir = BotaoSucesso("Abrir Caixa", icone_nome="wallet")
        self.bt_abrir.setFixedWidth(200)
        self.bt_abrir.setMinimumHeight(46)
        self.bt_abrir.clicked.connect(self.abrir_caixa)

        layout.addWidget(icone, alignment=Qt.AlignHCenter)
        layout.addWidget(titulo)
        layout.addWidget(subtitulo, alignment=Qt.AlignHCenter)
        layout.addSpacing(8)
        layout.addWidget(self.bt_abrir, alignment=Qt.AlignHCenter)

        return pagina

    # ======================================
    # PÁGINA · CAIXA ABERTO
    # ======================================

    def _criar_pagina_com_caixa(self):

        pagina = QWidget()

        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        # ---- faixa de status: situação, horário, previsto na gaveta e
        # as ações do turno (antes ficavam soltas no meio da página)

        status_frame = QFrame()
        status_frame.setObjectName("faixaStatusCaixa")
        status_frame.setStyleSheet(f"""
            #faixaStatusCaixa {{
                background:{tokens.SIDEBAR};
                border-radius:{tokens.RADIUS_MD}px;
            }}
        """)

        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(24, 18, 24, 18)
        status_layout.setSpacing(16)

        icone_status = QLabel()
        icone_status.setFixedSize(44, 44)
        icone_status.setAlignment(Qt.AlignCenter)
        icone_status.setStyleSheet(
            "background:rgba(255, 255, 255, 0.12); border-radius:22px;"
        )
        icone_status.setPixmap(icone_pixmap("wallet", cor="white", tamanho=20))
        status_layout.addWidget(icone_status)

        col_status = QVBoxLayout()
        col_status.setSpacing(4)

        linha_status = QHBoxLayout()
        linha_status.setSpacing(8)

        bolinha = QLabel()
        bolinha.setFixedSize(10, 10)
        bolinha.setStyleSheet(f"background:{tokens.SUCESSO}; border-radius:5px;")

        self.lbl_status = QLabel("Caixa aberto")
        self.lbl_status.setStyleSheet(f"""
            background:transparent; color:white;
            font-size:{tokens.TAMANHO_LG}px; font-weight:800;
        """)

        linha_status.addWidget(bolinha)
        linha_status.addWidget(self.lbl_status)
        linha_status.addStretch()

        self.lbl_abertura = QLabel("")
        self.lbl_abertura.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SIDEBAR};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        col_status.addLayout(linha_status)
        col_status.addWidget(self.lbl_abertura)

        status_layout.addLayout(col_status)
        status_layout.addStretch()

        col_total = QVBoxLayout()
        col_total.setSpacing(0)

        lbl_total_titulo = QLabel("Deve ter na gaveta")
        lbl_total_titulo.setAlignment(Qt.AlignRight)
        lbl_total_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SIDEBAR};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        self.lbl_total_previsto = QLabel("R$ 0,00")
        self.lbl_total_previsto.setAlignment(Qt.AlignRight)
        self.lbl_total_previsto.setStyleSheet(f"""
            background:transparent; color:white;
            font-size:{tokens.TAMANHO_XXL}px; font-weight:800;
        """)

        col_total.addWidget(lbl_total_titulo)
        col_total.addWidget(self.lbl_total_previsto)

        status_layout.addLayout(col_total)
        status_layout.addSpacing(12)

        # ações sobre o fundo escuro: contorno claro, e o Encerrar
        # preenchido (é o que fecha o turno)
        estilo_acao = f"""
            QPushButton {{
                background:rgba(255, 255, 255, 0.08); color:white;
                border:1px solid rgba(255, 255, 255, 0.22);
                border-radius:{tokens.RADIUS_SM}px; padding:0 16px;
                font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            }}
            QPushButton:hover {{ background:rgba(255, 255, 255, 0.16); }}
            QPushButton:disabled {{ color:rgba(255, 255, 255, 0.4); }}
        """

        self.bt_suprimento = QPushButton("  Suprimento")
        self.bt_suprimento.setIcon(icone("arrow-up", cor="white", tamanho=15))
        self.bt_suprimento.setToolTip("Colocar dinheiro na gaveta (ex.: troco extra)")
        self.bt_suprimento.setCursor(Qt.PointingHandCursor)
        self.bt_suprimento.setMinimumHeight(40)
        self.bt_suprimento.setStyleSheet(estilo_acao)
        self.bt_suprimento.clicked.connect(self.suprimento)

        self.bt_sangria = QPushButton("  Sangria")
        self.bt_sangria.setIcon(icone("arrow-down", cor="white", tamanho=15))
        self.bt_sangria.setToolTip("Tirar dinheiro da gaveta (ex.: levar ao cofre)")
        self.bt_sangria.setCursor(Qt.PointingHandCursor)
        self.bt_sangria.setMinimumHeight(40)
        self.bt_sangria.setStyleSheet(estilo_acao)
        self.bt_sangria.clicked.connect(self.sangria)

        self.bt_encerrar = QPushButton("  Encerrar caixa")
        self.bt_encerrar.setIcon(icone("log-out", cor=tokens.SIDEBAR, tamanho=15))
        self.bt_encerrar.setCursor(Qt.PointingHandCursor)
        self.bt_encerrar.setMinimumHeight(40)
        self.bt_encerrar.setStyleSheet(f"""
            QPushButton {{
                background:white; color:{tokens.SIDEBAR};
                border:none; border-radius:{tokens.RADIUS_SM}px; padding:0 16px;
                font-size:{tokens.TAMANHO_SM}px; font-weight:800;
            }}
            QPushButton:hover {{ background:{tokens.PRIMARIA_CLARA}; }}
        """)
        self.bt_encerrar.clicked.connect(self.fechar_caixa)
        self.bt_encerrar.setVisible(api.usuario_tem_permissao("caixa.fechar"))

        status_layout.addWidget(self.bt_suprimento)
        status_layout.addWidget(self.bt_sangria)
        status_layout.addWidget(self.bt_encerrar)

        layout.addWidget(status_frame)

        # ---- corpo: conferência (esquerda) + histórico (direita)

        corpo = QHBoxLayout()
        corpo.setSpacing(18)

        corpo.addWidget(self._criar_cartao_conferencia())

        # histórico
        col_historico = QVBoxLayout()
        col_historico.setSpacing(10)

        historico_cabecalho = QHBoxLayout()

        lbl_historico_titulo = QLabel("Movimentações do turno")
        lbl_historico_titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_MD}px;
            font-weight:700; color:{tokens.TEXTO};
        """)

        self.bt_atualizar_historico = BotaoSecundario("Atualizar", icone_nome="refresh-cw")
        self.bt_atualizar_historico.setMinimumHeight(32)
        self.bt_atualizar_historico.clicked.connect(self.carregar)

        self.bt_caixas_anteriores = BotaoSecundario("Caixas anteriores", icone_nome="calendar")
        self.bt_caixas_anteriores.setMinimumHeight(32)
        self.bt_caixas_anteriores.clicked.connect(self.abrir_caixas_anteriores)

        historico_cabecalho.addWidget(lbl_historico_titulo)
        historico_cabecalho.addStretch()
        historico_cabecalho.addWidget(self.bt_caixas_anteriores)
        historico_cabecalho.addWidget(self.bt_atualizar_historico)

        col_historico.addLayout(historico_cabecalho)

        self.tabela_movimentos = QTableWidget()
        self.tabela_movimentos.setColumnCount(4)
        self.tabela_movimentos.setHorizontalHeaderLabels(
            ["Data e hora", "Tipo", "Valor", "Descrição"]
        )
        cab = self.tabela_movimentos.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.Interactive)
        cab.setSectionResizeMode(3, QHeaderView.Stretch)
        cab.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.tabela_movimentos.setColumnWidth(0, 140)
        self.tabela_movimentos.setColumnWidth(1, 160)
        self.tabela_movimentos.setColumnWidth(2, 130)
        self.tabela_movimentos.verticalHeader().setVisible(False)
        self.tabela_movimentos.verticalHeader().setDefaultSectionSize(44)
        self.tabela_movimentos.setAlternatingRowColors(True)
        self.tabela_movimentos.setShowGrid(False)
        self.tabela_movimentos.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela_movimentos.setSelectionMode(QTableWidget.NoSelection)
        self.tabela_movimentos.setFocusPolicy(Qt.NoFocus)
        self.tabela_movimentos.setStyleSheet(f"""
            QTableWidget {{
                background:{tokens.CARD};
                alternate-background-color:{tokens.FUNDO};
                border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_MD}px;
                color:{tokens.TEXTO};
                font-size:{tokens.TAMANHO_BASE}px;
            }}
            QTableWidget::item {{
                color:{tokens.TEXTO};
                background:transparent;
                padding:0 12px;
            }}
            QHeaderView::section {{
                background:{tokens.CARD};
                color:{tokens.TEXTO_SECUNDARIO};
                padding:10px 12px;
                border:none;
                border-bottom:1px solid {tokens.BORDA};
                font-weight:700;
                font-size:{tokens.TAMANHO_XS}px;
            }}
        """)
        col_historico.addWidget(self.tabela_movimentos, stretch=1)

        self.lbl_sem_movimentos = QLabel(
            "Nenhuma movimentação ainda neste turno.\n"
            "Vendas, suprimentos e sangrias aparecem aqui."
        )
        self.lbl_sem_movimentos.setAlignment(Qt.AlignCenter)
        self.lbl_sem_movimentos.setStyleSheet(f"""
            background:{tokens.CARD}; border:1px dashed {tokens.BORDA};
            border-radius:{tokens.RADIUS_MD}px;
            color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_SM}px;
        """)
        self.lbl_sem_movimentos.setVisible(False)
        col_historico.addWidget(self.lbl_sem_movimentos, stretch=1)

        corpo.addLayout(col_historico, stretch=1)

        layout.addLayout(corpo, stretch=1)

        return pagina

    def _criar_cartao_conferencia(self):
        """Resumo do turno montado como a folha de fechamento de papel:
        uma conta que fecha no "deve ter na gaveta" e, separado, o que
        entrou por fora da gaveta (PIX, cartão). Antes eram 8 cards
        iguais e dois totais sem explicar a diferença entre eles."""

        cartao = QFrame()
        cartao.setObjectName("cartaoConferencia")
        cartao.setFixedWidth(400)
        cartao.setStyleSheet(f"""
            #cartaoConferencia {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_LG}px;
            }}
        """)

        lay = QVBoxLayout(cartao)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(8)

        def secao(texto):
            lbl = QLabel(texto.upper())
            lbl.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_XS}px; font-weight:800; letter-spacing:0.5px;
            """)
            lay.addWidget(lbl)

        def linha(rotulo, sinal="", destaque=False):
            caixa = QWidget()
            caixa.setStyleSheet("background:transparent;")
            h = QHBoxLayout(caixa)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(8)
            lbl_sinal = QLabel(sinal)
            lbl_sinal.setFixedWidth(14)
            lbl_sinal.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_MD}px; font-weight:700;
            """)
            lbl_rot = QLabel(rotulo)
            tamanho = tokens.TAMANHO_MD if destaque else tokens.TAMANHO_BASE
            lbl_rot.setStyleSheet(f"""
                background:transparent;
                color:{tokens.TEXTO if destaque else tokens.TEXTO_SECUNDARIO};
                font-size:{tamanho}px; font-weight:{800 if destaque else 500};
            """)
            lbl_valor = QLabel("R$ 0,00")
            lbl_valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl_valor.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO};
                font-size:{tokens.TAMANHO_LG if destaque else tokens.TAMANHO_BASE}px;
                font-weight:{800 if destaque else 600};
            """)
            h.addWidget(lbl_sinal)
            h.addWidget(lbl_rot, stretch=1)
            h.addWidget(lbl_valor)
            lay.addWidget(caixa)
            return caixa, lbl_valor

        def separador():
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
            lay.addSpacing(2)
            lay.addWidget(sep)
            lay.addSpacing(2)

        titulo = QLabel("Conferência do caixa")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:700;
        """)
        lay.addWidget(titulo)
        lay.addSpacing(8)

        secao("Dinheiro na gaveta")
        _, self.lbl_conf_troco = linha("Troco inicial")
        _, self.lbl_conf_dinheiro = linha("Vendas em dinheiro", "+")
        self.linha_conf_fiado_dinheiro, self.lbl_conf_fiado_dinheiro = linha(
            "Fiado recebido em dinheiro", "+"
        )
        _, self.lbl_conf_suprimentos = linha("Suprimentos", "+")
        _, self.lbl_conf_sangrias = linha("Sangrias", "−")
        separador()
        _, self.lbl_conf_gaveta = linha("Deve ter na gaveta", "=", destaque=True)

        lay.addSpacing(14)
        secao("Fora da gaveta")
        _, self.lbl_conf_pix = linha("PIX", "+")
        _, self.lbl_conf_cartao = linha("Cartão (débito e crédito)", "+")
        self.linha_conf_fiado_outros, self.lbl_conf_fiado_outros = linha(
            "Fiado recebido por PIX/cartão", "+"
        )
        separador()
        _, self.lbl_total_geral = linha("Total do turno", "=", destaque=True)

        lay.addStretch()

        # vendas a prazo não entram em nenhum total (o dinheiro ainda não
        # chegou) -- fica como nota, pra não parecer que sumiu
        self.lbl_conf_prazo = QLabel("")
        self.lbl_conf_prazo.setWordWrap(True)
        self.lbl_conf_prazo.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
            padding:10px 12px; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        lay.addWidget(self.lbl_conf_prazo)

        return cartao

    # ======================================
    # CARREGAR DADOS
    # ======================================

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            _buscar_dados_caixa,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_abrir.setEnabled(not carregando)
        self.bt_suprimento.setEnabled(not carregando)
        self.bt_sangria.setEnabled(not carregando)
        self.bt_encerrar.setEnabled(not carregando)
        self.bt_atualizar_historico.setEnabled(not carregando)

    def _ao_carregar_sucesso(self, resultado):
        try:
            caixa, resumo, movimentos = resultado

            if caixa is None:
                self.paginas.setCurrentWidget(self.pagina_sem_caixa)
                return

            resumo = resumo or {}

            self.lbl_abertura.setText(_texto_abertura(caixa.get("data_abertura")))

            def valor(chave):
                return float(resumo.get(chave, 0) or 0)

            troco = valor("saldo_inicial")
            dinheiro = valor("vendas_dinheiro")
            suprimentos = valor("suprimentos")
            sangrias = valor("sangrias")
            gaveta = valor("total_previsto")
            pix = valor("vendas_pix")
            cartao = valor("vendas_cartao")
            fiado = valor("recebimentos_fiado")

            # o backend não manda o fiado recebido em dinheiro separado,
            # mas ele é exatamente o que falta pra conta da gaveta fechar
            # (ver CaixaService.resumo: saldo_final já inclui essa parte)
            fiado_dinheiro = round(gaveta - troco - dinheiro - suprimentos + sangrias, 2)
            fiado_outros = round(fiado - fiado_dinheiro, 2)

            self.lbl_total_previsto.setText(formatar_moeda(gaveta))

            self.lbl_conf_troco.setText(formatar_moeda(troco))
            self.lbl_conf_dinheiro.setText(formatar_moeda(dinheiro))
            self.lbl_conf_fiado_dinheiro.setText(formatar_moeda(fiado_dinheiro))
            self.linha_conf_fiado_dinheiro.setVisible(abs(fiado_dinheiro) >= 0.01)
            self.lbl_conf_suprimentos.setText(formatar_moeda(suprimentos))
            self.lbl_conf_sangrias.setText(formatar_moeda(sangrias))
            self.lbl_conf_gaveta.setText(formatar_moeda(gaveta))

            self.lbl_conf_pix.setText(formatar_moeda(pix))
            self.lbl_conf_cartao.setText(formatar_moeda(cartao))
            self.lbl_conf_fiado_outros.setText(formatar_moeda(fiado_outros))
            self.linha_conf_fiado_outros.setVisible(abs(fiado_outros) >= 0.01)
            self.lbl_total_geral.setText(formatar_moeda(valor("total_geral")))

            prazo = valor("vendas_prazo")
            self.lbl_conf_prazo.setText(
                f"Vendas a prazo (fiado lançado): {formatar_moeda(prazo)}. "
                "Não entram nos totais porque o dinheiro ainda não chegou."
                if prazo >= 0.01 else
                "Vendas a prazo não entram nos totais: o dinheiro só conta "
                "quando o cliente paga."
            )

            self.carregar_movimentos(movimentos)

            self.paginas.setCurrentWidget(self.pagina_com_caixa)
        except Exception as erro:
            self._ao_carregar_erro(erro)

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar o caixa.\n{erro}"
        )

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    def carregar_movimentos(self, movimentos):

        movimentos = sorted(
            movimentos,
            key=lambda m: m.get("data", ""),
            reverse=True,
        )

        self.tabela_movimentos.setRowCount(len(movimentos))
        self.tabela_movimentos.setVisible(bool(movimentos))
        self.lbl_sem_movimentos.setVisible(not movimentos)

        for linha, mov in enumerate(movimentos):

            tipo = mov.get("tipo", "")

            self.tabela_movimentos.setItem(
                linha,
                0,
                QTableWidgetItem(_formatar_data_movimento(mov.get("data", ""))),
            )

            self.tabela_movimentos.setCellWidget(
                linha, 1, _pill_tipo_movimento(tipo)
            )

            self.tabela_movimentos.setCellWidget(
                linha,
                2,
                _celula_valor_movimento(tipo, formatar_moeda(mov.get("valor", 0))),
            )

            self.tabela_movimentos.setItem(
                linha,
                3,
                QTableWidgetItem(mov.get("descricao") or ""),
            )

    # ======================================
    # AÇÕES
    # ======================================

    def abrir_caixas_anteriores(self):
        from telas.caixas_anteriores import CaixasAnterioresDialog
        CaixasAnterioresDialog(parent=self).exec()

    def abrir_caixa(self):

        janela = AbrirCaixaWindow()

        if janela.exec() != QDialog.Accepted:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            abrir_caixa,
            janela.saldo,
            ao_sucesso=self._ao_abrir_caixa_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_abrir_caixa_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.warning(self, "Erro", erro)

    def _ao_mutacao_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutacao_finalizada(self):
        # se o sucesso da mutacao ja disparou carregar() de novo (abrir/
        # sangria/suprimento fazem isso), esse carregar() ja marcou
        # self._carregando=True antes de chegar aqui -- deixa ele mesmo
        # reabilitar os controles quando terminar, senao reabilitava
        # cedo demais (no meio do reload que ele proprio disparou)
        if not self._carregando:
            self._definir_controles_carregando(False)

    def fechar_caixa(self):

        janela = FecharCaixaWindow()

        if janela.exec() != QDialog.Accepted:
            return

        QMessageBox.information(
            self,
            "Sucesso",
            "Caixa fechado com sucesso!",
        )

        self.carregar()

    def sangria(self):

        janela = SangriaWindow()

        if janela.exec() != QDialog.Accepted:
            return

        dados = janela.dados

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            criar_sangria,
            dados["valor"],
            dados["descricao"],
            ao_sucesso=self._ao_movimento_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def suprimento(self):

        janela = SuprimentoWindow()

        if janela.exec() != QDialog.Accepted:
            return

        dados = janela.dados

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            criar_suprimento,
            dados["valor"],
            dados["descricao"],
            ao_sucesso=self._ao_movimento_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_movimento_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", erro)
