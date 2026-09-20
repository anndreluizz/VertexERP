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
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QDialog,
    QMessageBox,
    QScrollArea,
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
from design.widgets import Badge, BotaoPerigo, BotaoSecundario, BotaoSucesso, CardKPI
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
    layout.addWidget(pill)
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

        # ---- cabeçalho de status ----

        status_frame = QFrame()
        status_frame.setStyleSheet(f"""
            QFrame {{
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

        self.lbl_status = QLabel("CAIXA ABERTO")
        self.lbl_status.setStyleSheet(f"""
            background:transparent; color:white;
            font-size:{tokens.TAMANHO_LG}px; font-weight:800;
        """)

        linha_status.addWidget(bolinha)
        linha_status.addWidget(self.lbl_status)
        linha_status.addStretch()

        self.lbl_abertura = QLabel("Aberto em --")
        self.lbl_abertura.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SIDEBAR};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_status.addLayout(linha_status)
        col_status.addWidget(self.lbl_abertura)

        status_layout.addLayout(col_status)
        status_layout.addStretch()

        col_total = QVBoxLayout()
        col_total.setSpacing(2)

        lbl_total_titulo = QLabel("TOTAL PREVISTO NA GAVETA")
        lbl_total_titulo.setAlignment(Qt.AlignRight)
        lbl_total_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SIDEBAR};
            font-size:{tokens.TAMANHO_XS}px;
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

        layout.addWidget(status_frame)

        # ---- area rolavel (cards, acoes e historico) -- so o status
        # acima fica fixo, o resto rola quando nao couber na tela ----

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        conteudo = QWidget()
        conteudo.setStyleSheet("background:transparent;")

        conteudo_layout = QVBoxLayout(conteudo)
        conteudo_layout.setContentsMargins(0, 0, 0, 0)
        conteudo_layout.setSpacing(18)

        scroll.setWidget(conteudo)
        layout.addWidget(scroll, stretch=1)

        # ---- cards de resumo ----

        cards_layout = QGridLayout()
        cards_layout.setSpacing(14)

        self.card_troco = CardKPI("Troco inicial", "wallet", tokens.PRIMARIA)
        self.card_dinheiro = CardKPI("Vendas em dinheiro", "dollar-sign", tokens.SECUNDARIA)
        self.card_pix = CardKPI("Vendas PIX", "credit-card", tokens.PRIMARIA)
        self.card_cartao = CardKPI("Vendas cartão", "credit-card", tokens.PRIMARIA)
        self.card_suprimentos = CardKPI("Suprimentos", "arrow-up", tokens.SECUNDARIA)
        self.card_sangrias = CardKPI("Sangrias", "arrow-down", tokens.ERRO)
        self.card_prazo = CardKPI("Vendas a prazo", "file-text", tokens.TEXTO_SECUNDARIO)
        self.card_recebimentos_fiado = CardKPI(
            "Recebimentos fiado", "check", tokens.SECUNDARIA
        )

        cards_layout.addWidget(self.card_troco, 0, 0)
        cards_layout.addWidget(self.card_dinheiro, 0, 1)
        cards_layout.addWidget(self.card_pix, 0, 2)
        cards_layout.addWidget(self.card_cartao, 0, 3)
        cards_layout.addWidget(self.card_suprimentos, 1, 0)
        cards_layout.addWidget(self.card_sangrias, 1, 1)
        cards_layout.addWidget(self.card_prazo, 1, 2)
        cards_layout.addWidget(self.card_recebimentos_fiado, 1, 3)

        for coluna in range(4):
            cards_layout.setColumnStretch(coluna, 1)

        conteudo_layout.addLayout(cards_layout)

        # ---- total geral do turno -- destacado à parte dos demais
        # cards porque é a soma de tudo, não mais um indicador entre
        # iguais ----

        total_frame = QFrame()
        total_frame.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; border-radius:{tokens.RADIUS_MD}px;
        """)

        total_layout = QHBoxLayout(total_frame)
        total_layout.setContentsMargins(20, 16, 20, 16)
        total_layout.setSpacing(14)

        icone_total = QLabel()
        icone_total.setFixedSize(40, 40)
        icone_total.setAlignment(Qt.AlignCenter)
        icone_total.setStyleSheet(f"background:{tokens.CARD}; border-radius:20px;")
        icone_total.setPixmap(icone_pixmap("trending-up", cor=tokens.PRIMARIA, tamanho=18))
        total_layout.addWidget(icone_total)

        lbl_total_rotulo = QLabel("TOTAL GERAL DO TURNO")
        lbl_total_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.PRIMARIA_HOVER};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)
        total_layout.addWidget(lbl_total_rotulo)
        total_layout.addStretch()

        self.lbl_total_geral = QLabel("R$ 0,00")
        self.lbl_total_geral.setStyleSheet(f"""
            background:transparent; color:{tokens.PRIMARIA};
            font-size:{tokens.TAMANHO_XXL}px; font-weight:800;
        """)
        total_layout.addWidget(self.lbl_total_geral)

        conteudo_layout.addWidget(total_frame)

        # ---- ações ----

        acoes_layout = QHBoxLayout()
        acoes_layout.setSpacing(10)

        self.bt_suprimento = BotaoSucesso("+ Suprimento", icone_nome="arrow-up")
        self.bt_suprimento.setMinimumHeight(46)
        self.bt_suprimento.clicked.connect(self.suprimento)

        self.bt_sangria = BotaoPerigo("- Sangria", icone_nome="arrow-down")
        self.bt_sangria.setMinimumHeight(46)
        self.bt_sangria.clicked.connect(self.sangria)

        self.bt_encerrar = QPushButton("Encerrar Caixa")
        self.bt_encerrar.setCursor(Qt.PointingHandCursor)
        self.bt_encerrar.setMinimumHeight(46)
        self.bt_encerrar.setIcon(icone("log-out", cor="white", tamanho=16))
        self.bt_encerrar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.SIDEBAR}; color:white;
                border-radius:{tokens.RADIUS_SM}px; padding:0 22px; font-weight:700;
            }}
            QPushButton:hover {{ background:{tokens.SIDEBAR_HOVER}; }}
        """)
        self.bt_encerrar.clicked.connect(self.fechar_caixa)
        self.bt_encerrar.setVisible(api.usuario_tem_permissao("caixa.fechar"))

        acoes_layout.addWidget(self.bt_suprimento)
        acoes_layout.addWidget(self.bt_sangria)
        acoes_layout.addStretch()
        acoes_layout.addWidget(self.bt_encerrar)

        conteudo_layout.addLayout(acoes_layout)

        # ---- histórico de movimentações ----

        historico_cabecalho = QHBoxLayout()

        lbl_historico_titulo = QLabel("HISTÓRICO DO CAIXA")
        lbl_historico_titulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_XS}px; font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        self.bt_atualizar_historico = BotaoSecundario("Atualizar", icone_nome="refresh-cw")
        self.bt_atualizar_historico.setMinimumHeight(32)
        self.bt_atualizar_historico.clicked.connect(self.carregar)

        historico_cabecalho.addWidget(lbl_historico_titulo)
        historico_cabecalho.addStretch()
        historico_cabecalho.addWidget(self.bt_atualizar_historico)

        conteudo_layout.addLayout(historico_cabecalho)

        self.tabela_movimentos = QTableWidget()
        self.tabela_movimentos.setColumnCount(4)
        self.tabela_movimentos.setHorizontalHeaderLabels(
            ["Data/Hora", "Tipo", "Valor", "Descrição"]
        )
        self.tabela_movimentos.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela_movimentos.verticalHeader().setVisible(False)
        self.tabela_movimentos.setAlternatingRowColors(True)
        self.tabela_movimentos.setEditTriggers(
            QTableWidget.NoEditTriggers
        )
        self.tabela_movimentos.setSelectionMode(
            QTableWidget.NoSelection
        )
        self.tabela_movimentos.setFocusPolicy(Qt.NoFocus)
        self.tabela_movimentos.setStyleSheet(f"""
            QTableWidget {{
                background:{tokens.CARD};
                alternate-background-color:{tokens.FUNDO};
                border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_MD}px;
                gridline-color:{tokens.BORDA};
                color:{tokens.TEXTO};
                font-size:{tokens.TAMANHO_BASE}px;
            }}
            QTableWidget::item {{
                color:{tokens.TEXTO};
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

        self.tabela_movimentos.setMinimumHeight(300)
        conteudo_layout.addWidget(self.tabela_movimentos)

        conteudo_layout.addStretch()

        return pagina

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

            data_abertura = str(caixa.get("data_abertura", ""))[:16]
            data_abertura = data_abertura.replace("T", " ")

            self.lbl_abertura.setText(f"Aberto em {data_abertura}")

            total_previsto = float(resumo.get("total_previsto", 0) or 0)
            self.lbl_total_previsto.setText(formatar_moeda(total_previsto))

            self.card_troco.definir_valor(
                formatar_moeda(resumo.get("saldo_inicial", 0))
            )
            self.card_dinheiro.definir_valor(
                formatar_moeda(resumo.get("vendas_dinheiro", 0))
            )
            self.card_pix.definir_valor(
                formatar_moeda(resumo.get("vendas_pix", 0))
            )
            self.card_cartao.definir_valor(
                formatar_moeda(resumo.get("vendas_cartao", 0))
            )
            self.card_suprimentos.definir_valor(
                f"+ {formatar_moeda(resumo.get('suprimentos', 0))}"
            )
            self.card_sangrias.definir_valor(
                f"- {formatar_moeda(resumo.get('sangrias', 0))}"
            )
            self.card_prazo.definir_valor(
                formatar_moeda(resumo.get("vendas_prazo", 0))
            )
            self.card_recebimentos_fiado.definir_valor(
                formatar_moeda(resumo.get("recebimentos_fiado", 0))
            )
            self.lbl_total_geral.setText(
                formatar_moeda(resumo.get("total_geral", 0))
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
