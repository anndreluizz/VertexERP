import csv

from PySide6.QtWidgets import QMessageBox

from telas.cadastro_cliente import CadastroClienteDialog
from telas.ficha_cliente import FichaClienteDialog

from services.cliente_service import listar_clientes, reativar_cliente
from services.movimento_fiado_service import listar_movimentos
from services.venda_service import listar_vendas
from services import cliente_analise

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QShortcut, QKeySequence

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QDialog,
    QComboBox,
    QFileDialog,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import Avatar, Badge, BotaoPrimario, BotaoSecundario, CampoTexto, CardKPI
from utils.formatacao import formatar_moeda


# rótulo exibido -> chave interna do filtro
FILTROS = [
    ("Todos", "TODOS"),
    ("Clientes Ativos", "ATIVOS"),
    ("Sem Movimento", "SEM_MOVIMENTO"),
    ("Inadimplentes", "INADIMPLENTES"),
    ("Em Dia", "EM_DIA"),
    ("Novos Clientes", "NOVOS"),
]

# icone (lucide) de cada filtro -- nao ha "clock" no pacote baixado,
# "calendar" fica o mais proximo pra "Sem Movimento"
_ICONES_FILTRO = {
    "TODOS": "users",
    "ATIVOS": "user",
    "SEM_MOVIMENTO": "calendar",
    "INADIMPLENTES": "alert-triangle",
    "EM_DIA": "check",
    "NOVOS": "user",
}

# rótulo exibido -> chave interna da ordenação, na ordem que aparece no combo
ORDENACOES = [
    ("Último Movimento (mais recente primeiro)", "MOVIMENTO_RECENTE"),
    ("Último Movimento (mais antigo primeiro)", "MOVIMENTO_ANTIGO"),
    ("Última Compra", "ULTIMA_COMPRA"),
    ("Maior Compra", "MAIOR_COMPRA"),
    ("Maior Saldo Devedor", "MAIOR_SALDO"),
    ("Nome (A-Z)", "NOME_AZ"),
    ("Nome (Z-A)", "NOME_ZA"),
    ("Cliente Mais Antigo", "CADASTRO_ANTIGO"),
    ("Cliente Mais Novo", "CADASTRO_NOVO"),
]

_CORES_PONTUACAO = {
    "🔴": tokens.ERRO,
    "🟠": tokens.ALERTA,
    "🟡": tokens.ALERTA,
    "🔵": tokens.PRIMARIA,
    "🟢": tokens.SECUNDARIA,
}


class ClienteCard(QFrame):

    clicado = Signal(dict)
    reativar_solicitado = Signal(dict)

    def __init__(self, cliente, saldo_fiado, pontuacao="", ultima_movimentacao=None):

        super().__init__()

        self.cliente = cliente

        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border-radius: {tokens.RADIUS_LG}px;
                border: 1px solid {tokens.BORDA};
            }}
            QFrame:hover {{
                border: 1px solid {tokens.PRIMARIA};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        topo = QHBoxLayout()
        topo.setSpacing(12)

        avatar = Avatar(cliente.get("nome", ""), tamanho=44)

        col_nome = QVBoxLayout()
        col_nome.setSpacing(2)

        linha_nome = QHBoxLayout()
        linha_nome.setSpacing(8)

        nome = QLabel(cliente.get("nome") or "")
        nome.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tokens.TAMANHO_MD}px; font-weight:700; color:{tokens.TEXTO};
        """)

        ativo = cliente.get("ativo", True)

        badge = Badge("Ativo" if ativo else "Inativo", "sucesso" if ativo else "erro")

        linha_nome.addWidget(nome)
        linha_nome.addWidget(badge)
        linha_nome.addStretch()

        contato = cliente.get("telefone") or "Sem telefone"

        lbl_contato = QLabel(contato)
        lbl_contato.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tokens.TAMANHO_SM}px; color:{tokens.TEXTO_SECUNDARIO};
        """)

        local = cliente.get("cidade") or cliente.get("endereco") or ""

        col_nome.addLayout(linha_nome)
        col_nome.addWidget(lbl_contato)

        if local:
            lbl_local = QLabel(local)
            lbl_local.setStyleSheet(f"""
                background:transparent; border:none;
                font-size:{tokens.TAMANHO_SM}px; color:{tokens.TEXTO_SECUNDARIO};
            """)
            col_nome.addWidget(lbl_local)

        topo.addWidget(avatar)
        topo.addLayout(col_nome, stretch=1)

        # menu de 3 pontos -- mesma acao de clicar no card (abrir a
        # ficha); nao duplica nenhum menu novo, so' mais um jeito de
        # chegar la', igual o resto do card ja permite
        bt_menu = QPushButton()
        bt_menu.setFixedSize(28, 28)
        bt_menu.setCursor(Qt.PointingHandCursor)
        bt_menu.setIcon(icone("more-vertical", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        bt_menu.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        bt_menu.clicked.connect(lambda: self.clicado.emit(self.cliente))
        topo.addWidget(bt_menu, 0, Qt.AlignTop)

        layout.addLayout(topo)

        if pontuacao:

            # tira o emoji do inicio (risco de nao renderizar em toda
            # maquina) -- a cor ja carrega o mesmo sinal visualmente
            emoji, _, texto_pontuacao = pontuacao.partition(" ")
            cor = _CORES_PONTUACAO.get(emoji, tokens.TEXTO_SECUNDARIO)

            lbl_pontuacao = QLabel(texto_pontuacao or pontuacao)
            lbl_pontuacao.setStyleSheet(f"""
                background:transparent; border:none;
                font-size:{tokens.TAMANHO_XS}px; font-weight:700; color:{cor};
            """)
            layout.addWidget(lbl_pontuacao)

        linha_stats = QHBoxLayout()
        linha_stats.setSpacing(10)

        cor_fiado = tokens.ERRO if saldo_fiado > 0 else tokens.SECUNDARIA
        linha_stats.addWidget(
            self._caixinha("dollar-sign", "Fiado", formatar_moeda(saldo_fiado), cor_fiado)
        )

        texto_data = (
            ultima_movimentacao.strftime("%d/%m/%Y") if ultima_movimentacao else "—"
        )
        linha_stats.addWidget(
            self._caixinha("calendar", "Último Movimento", texto_data, tokens.TEXTO)
        )

        layout.addLayout(linha_stats)

        bt_ver = BotaoSecundario("Ver cliente", icone_nome="user")
        bt_ver.setMinimumHeight(38)
        bt_ver.clicked.connect(lambda: self.clicado.emit(self.cliente))
        layout.addWidget(bt_ver)

        if not ativo:
            bt_reativar = QPushButton("Reativar")
            bt_reativar.setCursor(Qt.PointingHandCursor)
            bt_reativar.setMinimumHeight(34)
            bt_reativar.setStyleSheet(f"""
                QPushButton {{
                    background:{tokens.SECUNDARIA}; color:white;
                    border:none; border-radius:{tokens.RADIUS_SM}px;
                    font-size:{tokens.TAMANHO_SM}px;
                    font-weight:700;
                }}
                QPushButton:hover {{ background:{tokens.SECUNDARIA_HOVER}; }}
            """)
            bt_reativar.clicked.connect(
                lambda: self.reativar_solicitado.emit(self.cliente)
            )
            layout.addWidget(bt_reativar)

    def _caixinha(self, icone_nome, rotulo, valor, cor_valor):

        caixa = QFrame()
        caixa.setStyleSheet(f"""
            QFrame {{ background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px; }}
        """)

        cx_layout = QVBoxLayout(caixa)
        cx_layout.setContentsMargins(10, 8, 10, 8)
        cx_layout.setSpacing(3)

        topo_caixa = QHBoxLayout()
        topo_caixa.setSpacing(5)

        lbl_icone = QLabel()
        lbl_icone.setPixmap(icone_pixmap(icone_nome, cor=tokens.TEXTO_TERCIARIO, tamanho=12))
        lbl_icone.setStyleSheet("background:transparent; border:none;")
        topo_caixa.addWidget(lbl_icone)

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:10px; color:{tokens.TEXTO_TERCIARIO};
        """)
        topo_caixa.addWidget(lbl_rotulo)
        topo_caixa.addStretch()

        cx_layout.addLayout(topo_caixa)

        lbl_valor = QLabel(valor)
        lbl_valor.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:13px; font-weight:800; color:{cor_valor};
        """)
        cx_layout.addWidget(lbl_valor)

        return caixa

    def mousePressEvent(self, event):
        self.clicado.emit(self.cliente)
        super().mousePressEvent(event)


class Clientes(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.clientes = []
        self._clientes_filtrados = []
        self.vendas_por_cliente = {}
        self.agregados_por_cliente = {}
        self.filtro_status = "TODOS"
        self.ordenacao = "MOVIMENTO_RECENTE"
        self.prazo_inadimplencia = cliente_analise.PRAZO_INADIMPLENCIA_PADRAO

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

        icone_titulo = QLabel()
        icone_titulo.setFixedSize(36, 36)
        icone_titulo.setAlignment(Qt.AlignCenter)
        icone_titulo.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; border-radius:{tokens.RADIUS_SM}px;
        """)
        icone_titulo.setPixmap(icone_pixmap("users", cor=tokens.PRIMARIA, tamanho=18))

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Clientes")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            "Gerencie seus clientes, acompanhe o fiado e mantenha um "
            "bom relacionamento."
        )
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        self.bt_exportar = BotaoSecundario("Exportar CSV", icone_nome="download")
        self.bt_exportar.clicked.connect(self.exportar_csv)

        self.bt_novo = BotaoPrimario("Novo Cliente", icone_nome="plus")
        self.bt_novo.clicked.connect(self.novo_cliente)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addWidget(icone_titulo)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(self.bt_exportar)
        cabecalho.addWidget(self.bt_novo)

        layout.addLayout(cabecalho)

        # ======================
        # CARDS DE RESUMO
        # ======================

        resumo_layout = QGridLayout()
        resumo_layout.setSpacing(14)

        self.card_total = CardKPI("Cadastros (Total)", "users", tokens.PRIMARIA)
        self.card_ativos = CardKPI("Clientes Ativos", "check", tokens.SECUNDARIA)
        self.card_sem_movimento = CardKPI("Sem Movimento", "alert-triangle", tokens.ALERTA)
        self.card_inadimplentes = CardKPI("Inadimplentes", "alert-triangle", tokens.ERRO)
        self.card_recebido_fiado = CardKPI("Recebido de Fiado", "wallet", tokens.SECUNDARIA)
        self.card_a_receber = CardKPI("A Receber (Fiado em aberto)", "credit-card", tokens.ERRO)

        resumo_layout.addWidget(self.card_total, 0, 0)
        resumo_layout.addWidget(self.card_ativos, 0, 1)
        resumo_layout.addWidget(self.card_sem_movimento, 0, 2)
        resumo_layout.addWidget(self.card_inadimplentes, 0, 3)
        resumo_layout.addWidget(self.card_recebido_fiado, 0, 4)
        resumo_layout.addWidget(self.card_a_receber, 0, 5)

        for coluna in range(6):
            resumo_layout.setColumnStretch(coluna, 1)

        layout.addLayout(resumo_layout)

        # ======================
        # BUSCA + FILTRO
        # ======================

        barra = QHBoxLayout()
        barra.setSpacing(10)

        self.pesquisa = CampoTexto("Buscar por nome, telefone ou CPF/CNPJ...")
        self.pesquisa.textChanged.connect(self.filtrar_clientes)

        barra.addWidget(self.pesquisa, stretch=1)

        self.botoes_status = {}

        for rotulo, chave in FILTROS:

            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setMinimumHeight(44)
            bt.setIcon(icone(_ICONES_FILTRO.get(chave, "users"), cor=tokens.TEXTO_SECUNDARIO, tamanho=15))
            bt.clicked.connect(
                lambda checked, c=chave: self.selecionar_status(c)
            )

            self.botoes_status[chave] = bt
            barra.addWidget(bt)

        layout.addLayout(barra)

        # ======================
        # PRAZO DE INADIMPLÊNCIA + ORDENAÇÃO
        # ======================

        barra_ordenacao = QHBoxLayout()
        barra_ordenacao.setSpacing(10)

        lbl_prazo = QLabel("Prazo de inadimplência:")
        lbl_prazo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)

        self.combo_prazo = QComboBox()
        for dias in cliente_analise.PRAZOS_INADIMPLENCIA:
            self.combo_prazo.addItem(f"{dias} dias", dias)
        self.combo_prazo.setCurrentIndex(
            cliente_analise.PRAZOS_INADIMPLENCIA.index(
                cliente_analise.PRAZO_INADIMPLENCIA_PADRAO
            )
        )
        self.combo_prazo.setMinimumHeight(34)
        self.combo_prazo.currentIndexChanged.connect(self.alterar_prazo_inadimplencia)

        barra_ordenacao.addWidget(lbl_prazo)
        barra_ordenacao.addWidget(self.combo_prazo)

        barra_ordenacao.addSpacing(20)

        lbl_ordenar = QLabel("Ordenar por:")
        lbl_ordenar.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)
        barra_ordenacao.addWidget(lbl_ordenar)

        self.combo_ordenacao = QComboBox()
        for rotulo, chave in ORDENACOES:
            self.combo_ordenacao.addItem(rotulo, chave)
        self.combo_ordenacao.setMinimumHeight(34)
        self.combo_ordenacao.setMinimumWidth(260)
        self.combo_ordenacao.currentIndexChanged.connect(self.alterar_ordenacao)

        barra_ordenacao.addWidget(self.combo_ordenacao)

        barra_ordenacao.addStretch()

        self.lbl_contagem = QLabel("")
        self.lbl_contagem.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        barra_ordenacao.addWidget(self.lbl_contagem)

        layout.addLayout(barra_ordenacao)

        # ======================
        # GRID DE CLIENTES
        # ======================

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background:transparent;")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setAlignment(Qt.AlignTop)

        self.scroll.setWidget(self.grid_widget)

        layout.addWidget(self.scroll, stretch=1)

        self.lbl_vazio = QLabel(
            "Nenhum cliente cadastrado ainda.\n"
            "Clique em \"Novo Cliente\" pra começar o caderninho."
        )
        self.lbl_vazio.setAlignment(Qt.AlignCenter)
        self.lbl_vazio.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_BASE}px;
        """)
        self.lbl_vazio.setVisible(False)

        layout.addWidget(self.lbl_vazio)

        # ==========================================
        # ATALHOS DE TECLADO
        # ==========================================

        QShortcut(QKeySequence("F5"), self, self.carregar)
        QShortcut(QKeySequence("Ctrl+N"), self, self.novo_cliente)

        self.selecionar_status("TODOS")

        self.carregar()

    # ==========================================
    # CARREGAR CLIENTES
    # ==========================================

    def carregar(self):

        self.clientes = listar_clientes()

        # todos os movimentos de fiado numa unica chamada -- agrupa
        # por cliente aqui do lado de fora, em vez de bater 1 endpoint
        # por cliente (era assim que o saldo de cada card era buscado
        # antes, uma chamada HTTP por cliente na tela inteira).
        movimentos_fiado = listar_movimentos()

        movimentos_por_cliente = {}
        for mov in movimentos_fiado:
            cid = mov.get("cliente_id")
            if cid is None:
                continue
            movimentos_por_cliente.setdefault(cid, []).append(mov)

        self.agregados_por_cliente = {}

        for cliente in self.clientes:

            agr = cliente_analise.calcular_agregados(
                cliente, movimentos_por_cliente.get(cliente["id"], [])
            )

            self.agregados_por_cliente[cliente["id"]] = agr
            cliente["saldo_fiado"] = agr["saldo_devedor"]

        vendas = listar_vendas()

        self.vendas_por_cliente = {}

        for venda in vendas:

            cid = venda.get("cliente_id")

            if cid is None:
                continue

            self.vendas_por_cliente[cid] = (
                self.vendas_por_cliente.get(cid, 0)
                + float(venda.get("valor_total", 0) or 0)
            )

        # "Faturamento" somando venda.valor_total so contava vendas
        # com cliente vinculado (a maioria do PDV nao vincula) e ficava
        # sempre R$0,00 na pratica -- recebido de fiado e um numero
        # real que ja existe (MovimentoFiado tipo PAGAMENTO).
        self.recebido_fiado_total = sum(
            float(m.get("valor", 0) or 0)
            for m in movimentos_fiado
            if m.get("tipo") == "PAGAMENTO"
        )

        self.atualizar_cards_resumo()

        self.filtrar_clientes()

    # ==========================================
    # CARDS DE RESUMO
    # ==========================================

    def atualizar_cards_resumo(self):

        total = len(self.clientes)

        ativos = 0
        sem_movimento = 0
        inadimplentes = 0

        for cliente in self.clientes:

            agr = self.agregados_por_cliente.get(cliente["id"])

            if not agr:
                continue

            if cliente_analise.eh_ativo(agr):
                ativos += 1

            if cliente_analise.eh_sem_movimento(agr, self.prazo_inadimplencia):
                sem_movimento += 1

            if cliente_analise.eh_inadimplente(agr, self.prazo_inadimplencia):
                inadimplentes += 1

        total_a_receber = sum(
            float(c.get("saldo_fiado", 0) or 0) for c in self.clientes
        )

        self.card_total.definir_valor(str(total))
        self.card_ativos.definir_valor(str(ativos))
        self.card_sem_movimento.definir_valor(str(sem_movimento))
        self.card_inadimplentes.definir_valor(str(inadimplentes))
        self.card_recebido_fiado.definir_valor(
            formatar_moeda(self.recebido_fiado_total)
        )
        self.card_a_receber.definir_valor(formatar_moeda(total_a_receber))

    # ==========================================
    # FILTRO DE STATUS
    # ==========================================

    def selecionar_status(self, chave):

        self.filtro_status = chave

        for k, botao in self.botoes_status.items():

            selecionado = k == chave

            botao.setChecked(selecionado)
            botao.setIcon(icone(
                _ICONES_FILTRO.get(k, "users"),
                cor="white" if selecionado else tokens.TEXTO_SECUNDARIO,
                tamanho=15,
            ))

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.PRIMARIA if selecionado else tokens.CARD};
                    color: {"white" if selecionado else tokens.TEXTO};
                    border-radius: {tokens.RADIUS_SM}px;
                    border: 1px solid {tokens.PRIMARIA if selecionado else tokens.BORDA};
                    font-weight: 700;
                    font-size: {tokens.TAMANHO_SM}px;
                    padding: 0 14px;
                }}
                QPushButton:hover {{
                    background: {tokens.PRIMARIA_HOVER if selecionado else tokens.FUNDO};
                }}
            """)

        self.filtrar_clientes()

    # ==========================================
    # PRAZO DE INADIMPLÊNCIA
    # ==========================================

    def alterar_prazo_inadimplencia(self, _indice):

        self.prazo_inadimplencia = self.combo_prazo.currentData()

        self.atualizar_cards_resumo()
        self.filtrar_clientes()

    # ==========================================
    # ORDENAÇÃO
    # ==========================================

    def alterar_ordenacao(self, _indice):

        self.ordenacao = self.combo_ordenacao.currentData()

        self.filtrar_clientes()

    # ==========================================
    # FILTRAR CLIENTES
    # ==========================================

    def filtrar_clientes(self):

        texto = self.pesquisa.text().lower().strip()

        clientes = self.clientes

        def agr(c):
            return self.agregados_por_cliente.get(c["id"], {})

        if self.filtro_status == "ATIVOS":
            clientes = [
                c for c in clientes if cliente_analise.eh_ativo(agr(c))
            ]
        elif self.filtro_status == "SEM_MOVIMENTO":
            clientes = [
                c for c in clientes
                if cliente_analise.eh_sem_movimento(
                    agr(c), self.prazo_inadimplencia
                )
            ]
        elif self.filtro_status == "INADIMPLENTES":
            clientes = [
                c for c in clientes
                if cliente_analise.eh_inadimplente(
                    agr(c), self.prazo_inadimplencia
                )
            ]
        elif self.filtro_status == "EM_DIA":
            clientes = [
                c for c in clientes if cliente_analise.eh_em_dia(agr(c))
            ]
        elif self.filtro_status == "NOVOS":
            clientes = [
                c for c in clientes if cliente_analise.eh_novo(agr(c))
            ]

        if texto != "":

            filtrados = []

            for cliente in clientes:

                nome = str(cliente.get("nome") or "").lower()
                whatsapp = str(cliente.get("telefone") or "").lower()
                cpf = str(cliente.get("cpf_cnpj") or "").lower()

                if (
                    texto in nome
                    or texto in whatsapp
                    or texto in cpf
                ):
                    filtrados.append(cliente)

            clientes = filtrados

        clientes = self._ordenar(clientes)

        # guardado pra exportar exatamente o que esta na tela (filtro
        # + busca + ordenacao aplicados), nao a lista inteira sem filtro
        self._clientes_filtrados = clientes

        self.lbl_contagem.setText(
            "1 cliente encontrado" if len(clientes) == 1
            else f"{len(clientes)} clientes encontrados"
        )

        self.preencher_grid(clientes)

    def _ordenar(self, clientes):

        def agr(c):
            return self.agregados_por_cliente.get(c["id"], {})

        def nome(c):
            return (c.get("nome") or "").lower()

        # datas/numeros ausentes sempre vao pro final da lista,
        # independente da direcao da ordenacao
        def chave_data(campo, reverso):
            def _chave(c):
                valor = agr(c).get(campo)
                ausente = valor is None
                if reverso:
                    return (ausente, -valor.timestamp() if valor else 0)
                return (ausente, valor.timestamp() if valor else 0)
            return _chave

        if self.ordenacao == "MOVIMENTO_RECENTE":
            return sorted(
                clientes, key=chave_data("ultima_movimentacao", True)
            )
        if self.ordenacao == "MOVIMENTO_ANTIGO":
            return sorted(
                clientes, key=chave_data("ultima_movimentacao", False)
            )
        if self.ordenacao == "ULTIMA_COMPRA":
            return sorted(clientes, key=chave_data("ultima_compra", True))
        if self.ordenacao == "MAIOR_COMPRA":
            return sorted(
                clientes,
                key=lambda c: agr(c).get("maior_compra", 0),
                reverse=True,
            )
        if self.ordenacao == "MAIOR_SALDO":
            return sorted(
                clientes,
                key=lambda c: agr(c).get("saldo_devedor", 0),
                reverse=True,
            )
        if self.ordenacao == "NOME_ZA":
            return sorted(clientes, key=nome, reverse=True)
        if self.ordenacao == "CADASTRO_ANTIGO":
            return sorted(clientes, key=chave_data("criado_em", False))
        if self.ordenacao == "CADASTRO_NOVO":
            return sorted(clientes, key=chave_data("criado_em", True))

        # NOME_AZ e qualquer chave desconhecida caem aqui
        return sorted(clientes, key=nome)

    # ==========================================
    # PREENCHER GRID
    # ==========================================

    def preencher_grid(self, clientes):

        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        colunas = 3

        for indice, cliente in enumerate(clientes):

            agr = self.agregados_por_cliente.get(cliente["id"], {})
            pontuacao = (
                cliente_analise.calcular_pontuacao(
                    agr, self.prazo_inadimplencia
                )
                if agr else ""
            )

            card = ClienteCard(
                cliente,
                cliente.get("saldo_fiado", 0),
                pontuacao=pontuacao,
                ultima_movimentacao=agr.get("ultima_movimentacao"),
            )
            card.clicado.connect(self.ver_ficha)
            card.reativar_solicitado.connect(self.reativar_cliente)

            self.grid_layout.addWidget(
                card, indice // colunas, indice % colunas
            )

        self.scroll.setVisible(len(clientes) > 0)
        self.lbl_vazio.setVisible(len(clientes) == 0)

    # ==========================================
    # AÇÕES
    # ==========================================

    def novo_cliente(self):

        tela = CadastroClienteDialog(parent=self)

        if tela.exec() != QDialog.Accepted:
            return

        self.carregar()

    def ver_ficha(self, cliente):

        tela = FichaClienteDialog(cliente, parent=self)
        tela.exec()

        self.carregar()

    def reativar_cliente(self, cliente):

        resposta = QMessageBox.question(
            self,
            "Reativar Cliente",
            f"Reativar \"{cliente.get('nome')}\"?",
        )

        if resposta != QMessageBox.Yes:
            return

        response = reativar_cliente(cliente["id"])

        if response.status_code != 200:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
            return

        self.carregar()

    def exportar_csv(self):

        # exporta exatamente o que esta na tela agora (filtro + busca +
        # ordenacao aplicados), nao a base de clientes inteira
        if not self._clientes_filtrados:
            QMessageBox.information(
                self,
                "Nada para exportar",
                "Não há clientes na lista atual pra exportar.",
            )
            return

        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Clientes (CSV)",
            "clientes.csv",
            "Arquivo CSV (*.csv)",
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".csv"):
            caminho += ".csv"

        try:
            with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:

                escritor = csv.writer(arquivo, delimiter=";")
                escritor.writerow([
                    "Nome", "Telefone", "CPF/CNPJ", "E-mail",
                    "Saldo Devedor", "Última Movimentação", "Status",
                ])

                for cliente in self._clientes_filtrados:

                    agr = self.agregados_por_cliente.get(cliente["id"], {})

                    ultima_mov = agr.get("ultima_movimentacao")
                    texto_ultima_mov = (
                        ultima_mov.strftime("%d/%m/%Y") if ultima_mov else ""
                    )

                    escritor.writerow([
                        cliente.get("nome", ""),
                        cliente.get("telefone", "") or "",
                        cliente.get("cpf_cnpj", "") or "",
                        cliente.get("email", "") or "",
                        f"{float(cliente.get('saldo_fiado', 0) or 0):.2f}",
                        texto_ultima_mov,
                        "Ativo" if cliente.get("ativo", True) else "Inativo",
                    ])

            QMessageBox.information(
                self, "Sucesso", "Lista de clientes exportada com sucesso."
            )

        except OSError as erro:
            QMessageBox.critical(self, "Erro", str(erro))
