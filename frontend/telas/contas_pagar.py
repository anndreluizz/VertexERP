from datetime import date, datetime, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QScrollArea,
    QMessageBox,
)

from services.api import configuracoes
from services.categoria_despesa_service import listar_categorias_despesa
from services.conta_pagar_service import (
    listar_contas_pagar,
    excluir_conta_pagar,
)
from telas.cadastro_despesa import CadastroDespesaDialog
from telas.pagamento_despesa import PagamentoDespesaDialog

from design import tokens
from design.icons import icone
from design.widgets import Badge, BotaoPerigo, BotaoPrimario, BotaoSecundario, CampoTexto, Card, CardKPI


def _formatar_moeda(valor):
    return (
        f"R$ {float(valor):,.2f}".replace(",", "X")
        .replace(".", ",").replace("X", ".")
    )


def _status_real(conta):
    """PENDENTE com vencimento no passado vira VENCIDA na visualizacao
    — o backend nunca grava esse status, e essa e a unica derivacao
    que importa mostrar pro usuario (nao faz sentido gravar VENCIDA
    persistido, ja que o mesmo registro fica cada vez mais vencido
    conforme o tempo passa sem nenhuma acao)."""

    status = conta.get("status", "PENDENTE")

    if status != "PENDENTE":
        return status

    try:
        vencimento = datetime.fromisoformat(
            conta["data_vencimento"]
        ).date()
    except (ValueError, TypeError, KeyError):
        return status

    if vencimento < date.today():
        return "VENCIDA"

    return status


def _vencimento(conta):
    try:
        return datetime.fromisoformat(conta["data_vencimento"]).date()
    except (ValueError, TypeError, KeyError):
        return None


class DespesaCard(Card):

    editar_solicitado = Signal(dict)
    excluir_solicitado = Signal(dict)
    pagar_solicitado = Signal(dict)
    duplicar_solicitado = Signal(dict)

    VARIANTE_STATUS = {
        "PAGO": "sucesso",
        "PENDENTE": "alerta",
        "VENCIDA": "erro",
        "CANCELADO": "neutro",
    }

    TEXTO_STATUS = {
        "PAGO": "Paga",
        "PENDENTE": "Pendente",
        "VENCIDA": "Vencida",
        "CANCELADO": "Cancelada",
    }

    def __init__(self, conta):

        super().__init__()

        self.conta = conta

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        status = _status_real(conta)

        icone_cor = {
            "PAGO": tokens.SECUNDARIA,
            "PENDENTE": tokens.ALERTA,
            "VENCIDA": tokens.ERRO,
            "CANCELADO": tokens.TEXTO_TERCIARIO,
        }.get(status, tokens.TEXTO_TERCIARIO)

        icone_fundo = {
            "PAGO": tokens.SUCESSO_CLARO,
            "PENDENTE": tokens.ALERTA_CLARO,
            "VENCIDA": tokens.ERRO_CLARO,
            "CANCELADO": tokens.FUNDO,
        }.get(status, tokens.FUNDO)

        lbl_icone = QLabel()
        lbl_icone.setFixedSize(40, 40)
        lbl_icone.setAlignment(Qt.AlignCenter)
        lbl_icone.setStyleSheet(f"""
            background:{icone_fundo}; border-radius:20px;
        """)
        lbl_icone.setPixmap(
            icone("arrow-down", cor=icone_cor, tamanho=18).pixmap(18, 18)
        )

        layout.addWidget(lbl_icone)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(4)

        topo = QHBoxLayout()
        topo.setSpacing(8)

        badge_status = Badge(
            self.TEXTO_STATUS.get(status, status),
            self.VARIANTE_STATUS.get(status, "neutro"),
        )
        topo.addWidget(badge_status)

        categoria = conta.get("categoria")

        if categoria:
            badge_categoria = QLabel(categoria.upper())
            badge_categoria.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_XS}px; font-weight:700; border:none;
            """)
            topo.addWidget(badge_categoria)

        topo.addStretch()

        col_texto.addLayout(topo)

        descricao = QLabel(conta.get("descricao") or "Despesa")
        descricao.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_MD}px;
            font-weight:700; color:{tokens.TEXTO};
        """)
        col_texto.addWidget(descricao)

        vencimento_formatado = _vencimento(conta)
        texto_vencimento = (
            vencimento_formatado.strftime("%d/%m/%Y")
            if vencimento_formatado else conta.get("data_vencimento", "")
        )

        # Pendente com vencimento hoje ou amanha esquenta pra vermelho
        # antes mesmo de virar "Vencida" — aviso com um dia de antecedencia
        # (vencido de verdade ja vira status VENCIDA, tratado acima).
        vence_em_breve = (
            status == "PENDENTE"
            and vencimento_formatado is not None
            and (vencimento_formatado - date.today()).days <= 1
        )

        cor_vencimento = tokens.ERRO if vence_em_breve else tokens.TEXTO

        lbl_vencimento = QLabel(f"Vencimento: {texto_vencimento}")
        lbl_vencimento.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_MD}px;
            font-weight:700; color:{cor_vencimento};
        """)
        col_texto.addWidget(lbl_vencimento)

        layout.addLayout(col_texto, stretch=1)

        lbl_valor = QLabel(_formatar_moeda(conta.get("valor", 0)))
        lbl_valor.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        layout.addWidget(lbl_valor)

        acoes = QHBoxLayout()
        acoes.setSpacing(6)

        if status in ("PENDENTE", "VENCIDA"):

            bt_pagar = BotaoSecundario("Pagar", icone_nome="check")
            bt_pagar.clicked.connect(
                lambda: self.pagar_solicitado.emit(self.conta)
            )
            acoes.addWidget(bt_pagar)

        acoes.addWidget(self._botao_icone("edit-2", self.editar_solicitado))
        acoes.addWidget(self._botao_icone("file-text", self.duplicar_solicitado))
        acoes.addWidget(self._botao_icone("trash-2", self.excluir_solicitado, perigo=True))

        layout.addLayout(acoes)

    def _botao_icone(self, icone_nome, sinal, perigo=False):

        bt = QPushButton()
        bt.setFixedSize(34, 34)
        bt.setCursor(Qt.PointingHandCursor)

        cor = tokens.ERRO if perigo else tokens.TEXTO_SECUNDARIO
        fundo_hover = tokens.ERRO_CLARO if perigo else tokens.FUNDO

        bt.setIcon(icone(icone_nome, cor=cor, tamanho=15))
        bt.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px; border:none;
            }}
            QPushButton:hover {{ background:{fundo_hover}; }}
        """)
        bt.clicked.connect(lambda: sinal.emit(self.conta))

        return bt


class ContasPagar(QWidget):

    voltar = Signal()

    FILTROS_STATUS = ["TODAS", "PAGA", "PENDENTE", "VENCIDA"]
    FILTROS_PERIODO = [
        ("TODOS", "Todos"),
        ("HOJE", "Hoje"),
        ("SEMANA", "Semana"),
        ("MES", "Mês"),
        ("ANO", "Ano"),
    ]

    def __init__(self):
        super().__init__()

        self.contas = []
        self.filtro_status = "TODAS"
        self.filtro_periodo = "TODOS"

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

        config = configuracoes()
        nome_loja = config.get("nome_loja") or "Vertex ERP"

        titulo = QLabel(nome_loja)
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel("CONTAS A PAGAR")
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.SECUNDARIA_HOVER}; font-weight:700;
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addSpacing(4)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()

        self.bt_nova_despesa = BotaoPerigo("Nova Despesa", icone_nome="plus")
        self.bt_nova_despesa.clicked.connect(self.nova_despesa)

        cabecalho.addWidget(self.bt_nova_despesa)

        layout.addLayout(cabecalho)

        # ======================
        # KPIS
        # ======================

        kpis_layout = QGridLayout()
        kpis_layout.setSpacing(14)

        self.card_previsao = CardKPI("Total Previsto", "file-text", tokens.PRIMARIA)
        self.card_pago = CardKPI("Pago", "check", tokens.SECUNDARIA)
        self.card_aberto = CardKPI("Em Aberto", "wallet", tokens.ALERTA)
        self.card_vencidas = CardKPI("Vencidas", "alert-triangle", tokens.ERRO)
        self.card_vence_hoje = CardKPI("Vence Hoje", "calendar", tokens.ERRO)
        self.card_proximos_7 = CardKPI("Próximos 7 dias", "trending-up", tokens.ALERTA)
        self.card_valor_medio = CardKPI("Valor Médio", "dollar-sign", tokens.PRIMARIA)

        cartoes = [
            self.card_previsao, self.card_pago, self.card_aberto, self.card_vencidas,
            self.card_vence_hoje, self.card_proximos_7, self.card_valor_medio,
        ]

        for i, card in enumerate(cartoes):
            kpis_layout.addWidget(card, i // 4, i % 4)

        for coluna in range(4):
            kpis_layout.setColumnStretch(coluna, 1)

        # kpis_layout entra dentro da area de rolagem mais abaixo, nao
        # aqui direto — ver secao LISTA.

        # ======================
        # FILTROS
        # ======================

        linha_busca = QHBoxLayout()
        linha_busca.setSpacing(10)

        self.pesquisa = CampoTexto("Buscar por descrição ou categoria...")
        self.pesquisa.textChanged.connect(self._renderizar_lista)
        linha_busca.addWidget(self.pesquisa, stretch=1)

        self.combo_categoria = QComboBox()
        self.combo_categoria.setMinimumHeight(44)
        self.combo_categoria.setMinimumWidth(180)
        self.combo_categoria.setCursor(Qt.PointingHandCursor)
        self.combo_categoria.setStyleSheet(f"""
            QComboBox {{
                border:1.5px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:0 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """)
        self.combo_categoria.currentTextChanged.connect(self._renderizar_lista)
        linha_busca.addWidget(self.combo_categoria)

        layout.addLayout(linha_busca)

        linha_filtros = QHBoxLayout()
        linha_filtros.setSpacing(20)

        self.botoes_status = {}

        grupo_status = QHBoxLayout()
        grupo_status.setSpacing(8)

        for filtro in self.FILTROS_STATUS:

            botao = QPushButton(filtro.capitalize())
            botao.setCheckable(True)
            botao.setCursor(Qt.PointingHandCursor)
            botao.setMinimumHeight(34)
            botao.clicked.connect(
                lambda _checked, f=filtro: self._filtrar_status(f)
            )

            self.botoes_status[filtro] = botao
            grupo_status.addWidget(botao)

        linha_filtros.addLayout(grupo_status)

        linha_filtros.addWidget(self._separador_vertical())

        self.botoes_periodo = {}

        grupo_periodo = QHBoxLayout()
        grupo_periodo.setSpacing(8)

        for chave, rotulo in self.FILTROS_PERIODO:

            botao = QPushButton(rotulo)
            botao.setCheckable(True)
            botao.setCursor(Qt.PointingHandCursor)
            botao.setMinimumHeight(34)
            botao.clicked.connect(
                lambda _checked, f=chave: self._filtrar_periodo(f)
            )

            self.botoes_periodo[chave] = botao
            grupo_periodo.addWidget(botao)

        linha_filtros.addLayout(grupo_periodo)
        linha_filtros.addStretch()

        layout.addLayout(linha_filtros)

        self._estilizar_pills(self.botoes_status, self.filtro_status)
        self._estilizar_pills(self.botoes_periodo, self.filtro_periodo)

        # ======================
        # KPIS + LISTA (rolam juntos)
        # ======================

        # Os KPIs entram dentro da mesma area de rolagem que a lista —
        # antes ficavam fixos no topo e tomavam boa parte da tela,
        # sobrando pouco espaco pra ver os boletos. Rolando pra baixo
        # agora o dashboard sai da tela e a lista ganha o espaco todo;
        # cabecalho, busca e filtros continuam fixos.

        self.area_rolagem = QScrollArea()
        self.area_rolagem.setWidgetResizable(True)
        self.area_rolagem.setStyleSheet(
            "QScrollArea { border:none; background:transparent; }"
        )

        conteudo_rolavel = QWidget()
        conteudo_rolavel.setStyleSheet("background:transparent;")

        conteudo_layout = QVBoxLayout(conteudo_rolavel)
        conteudo_layout.setContentsMargins(0, 0, 0, 0)
        conteudo_layout.setSpacing(16)

        conteudo_layout.addLayout(kpis_layout)

        self.lista_layout = QVBoxLayout()
        self.lista_layout.setSpacing(10)
        self.lista_layout.setAlignment(Qt.AlignTop)

        conteudo_layout.addLayout(self.lista_layout)

        self.area_rolagem.setWidget(conteudo_rolavel)

        layout.addWidget(self.area_rolagem, stretch=1)

    def _separador_vertical(self):

        linha = QLabel()
        linha.setFixedWidth(1)
        linha.setFixedHeight(30)
        linha.setStyleSheet(f"background:{tokens.BORDA};")
        return linha

    def _estilizar_pills(self, botoes, ativo):

        for chave, botao in botoes.items():

            selecionado = chave == ativo

            botao.setChecked(selecionado)

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.SIDEBAR if selecionado else tokens.CARD};
                    color: {"white" if selecionado else tokens.TEXTO};
                    border: 1px solid {tokens.SIDEBAR if selecionado else tokens.BORDA};
                    border-radius: {tokens.RADIUS_PILL}px;
                    padding: 0 16px; font-size: {tokens.TAMANHO_SM}px; font-weight: 700;
                }}
                QPushButton:hover {{
                    background: {"#33363b" if selecionado else tokens.FUNDO};
                }}
            """)

    # ==========================================
    # CARREGAMENTO
    # ==========================================

    def carregar(self):

        self.contas = listar_contas_pagar()

        self._carregar_categorias()
        self._atualizar_kpis()
        self._renderizar_lista()

    def _carregar_categorias(self):

        selecionada = self.combo_categoria.currentText()

        self.combo_categoria.blockSignals(True)
        self.combo_categoria.clear()
        self.combo_categoria.addItem("Todas as categorias")

        nomes = sorted({
            c.get("categoria") for c in self.contas if c.get("categoria")
        })
        self.combo_categoria.addItems(nomes)

        if selecionada and self.combo_categoria.findText(selecionada) >= 0:
            self.combo_categoria.setCurrentText(selecionada)

        self.combo_categoria.blockSignals(False)

    def _atualizar_kpis(self):

        contas_validas = [
            c for c in self.contas
            if c.get("status") != "CANCELADO"
        ]

        hoje = date.today()

        previsao_total = sum(
            float(c.get("valor", 0)) for c in contas_validas
        )

        total_pago = sum(
            float(c.get("valor", 0)) for c in contas_validas
            if c.get("status") == "PAGO"
        )

        em_aberto = sum(
            float(c.get("valor", 0)) for c in contas_validas
            if _status_real(c) == "PENDENTE"
        )

        vencidas_lista = [
            c for c in contas_validas
            if _status_real(c) == "VENCIDA"
        ]
        vencidas_total = sum(float(c.get("valor", 0)) for c in vencidas_lista)

        vence_hoje_total = sum(
            float(c.get("valor", 0)) for c in contas_validas
            if _status_real(c) == "PENDENTE" and _vencimento(c) == hoje
        )

        limite_7 = hoje + timedelta(days=7)
        proximos_7_total = sum(
            float(c.get("valor", 0)) for c in contas_validas
            if _status_real(c) == "PENDENTE"
            and _vencimento(c) is not None
            and hoje < _vencimento(c) <= limite_7
        )

        valor_medio = (
            previsao_total / len(contas_validas) if contas_validas else 0
        )

        self.card_previsao.definir_valor(_formatar_moeda(previsao_total))
        self.card_pago.definir_valor(_formatar_moeda(total_pago))
        self.card_aberto.definir_valor(_formatar_moeda(em_aberto))
        self.card_vencidas.definir_valor(_formatar_moeda(vencidas_total))
        self.card_vence_hoje.definir_valor(_formatar_moeda(vence_hoje_total))
        self.card_proximos_7.definir_valor(_formatar_moeda(proximos_7_total))
        self.card_valor_medio.definir_valor(_formatar_moeda(valor_medio))

    def _filtrar_status(self, filtro):

        self.filtro_status = filtro
        self._estilizar_pills(self.botoes_status, filtro)
        self._renderizar_lista()

    def _filtrar_periodo(self, filtro):

        self.filtro_periodo = filtro
        self._estilizar_pills(self.botoes_periodo, filtro)
        self._renderizar_lista()

    def _dentro_do_periodo(self, conta):

        if self.filtro_periodo == "TODOS":
            return True

        venc = _vencimento(conta)

        if venc is None:
            return False

        hoje = date.today()

        if self.filtro_periodo == "HOJE":
            return venc == hoje

        if self.filtro_periodo == "SEMANA":
            return hoje <= venc <= hoje + timedelta(days=7)

        if self.filtro_periodo == "MES":
            return venc.year == hoje.year and venc.month == hoje.month

        if self.filtro_periodo == "ANO":
            return venc.year == hoje.year

        return True

    def _renderizar_lista(self):

        while self.lista_layout.count():
            item = self.lista_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if self.filtro_status == "TODAS":
            contas_filtradas = [
                c for c in self.contas
                if c.get("status") != "CANCELADO"
            ]
        else:
            contas_filtradas = [
                c for c in self.contas
                if _status_real(c) == self.filtro_status
            ]

        contas_filtradas = [
            c for c in contas_filtradas if self._dentro_do_periodo(c)
        ]

        categoria_selecionada = self.combo_categoria.currentText()
        if categoria_selecionada and categoria_selecionada != "Todas as categorias":
            contas_filtradas = [
                c for c in contas_filtradas
                if c.get("categoria") == categoria_selecionada
            ]

        texto = self.pesquisa.text().lower().strip()
        if texto:
            contas_filtradas = [
                c for c in contas_filtradas
                if texto in str(c.get("descricao") or "").lower()
                or texto in str(c.get("categoria") or "").lower()
            ]

        if not contas_filtradas:

            lbl_vazio = QLabel(
                "Nenhuma despesa encontrada com esses filtros."
            )
            lbl_vazio.setAlignment(Qt.AlignCenter)
            lbl_vazio.setStyleSheet(f"""
                color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_BASE}px;
                padding:40px; background:transparent;
            """)
            self.lista_layout.addWidget(lbl_vazio)
            return

        contas_ordenadas = sorted(
            contas_filtradas,
            key=lambda c: c.get("data_vencimento", ""),
        )

        for conta in contas_ordenadas:

            card = DespesaCard(conta)
            card.editar_solicitado.connect(self.editar_despesa)
            card.excluir_solicitado.connect(self.excluir_despesa)
            card.pagar_solicitado.connect(self.pagar_despesa)
            card.duplicar_solicitado.connect(self.duplicar_despesa)

            self.lista_layout.addWidget(card)

    # ==========================================
    # AÇÕES
    # ==========================================

    def nova_despesa(self):

        dialogo = CadastroDespesaDialog(parent=self)

        if dialogo.exec() == dialogo.DialogCode.Accepted:
            self.carregar()

    def editar_despesa(self, conta):

        dialogo = CadastroDespesaDialog(conta=conta, parent=self)

        if dialogo.exec() == dialogo.DialogCode.Accepted:
            self.carregar()

    def duplicar_despesa(self, conta):

        dialogo = CadastroDespesaDialog(duplicar_de=conta, parent=self)

        if dialogo.exec() == dialogo.DialogCode.Accepted:
            self.carregar()

    def excluir_despesa(self, conta):

        resposta = QMessageBox.question(
            self,
            "Excluir despesa",
            f"Excluir a despesa \"{conta.get('descricao')}\"?",
        )

        if resposta != QMessageBox.Yes:
            return

        response = excluir_conta_pagar(conta["id"])

        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def pagar_despesa(self, conta):

        dialogo = PagamentoDespesaDialog(conta, parent=self)

        if dialogo.exec() == dialogo.DialogCode.Accepted:
            self.carregar()
