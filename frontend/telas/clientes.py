from PySide6.QtWidgets import QMessageBox

from telas.cadastro_cliente import CadastroClienteDialog
from telas.ficha_cliente import FichaClienteDialog

from services.api import configuracoes
from services.cliente_service import listar_clientes
from services.movimento_fiado_service import saldo_cliente
from services.venda_service import listar_vendas

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
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import Avatar, Badge, BotaoPrimario, BotaoSecundario, CampoTexto, CardKPI


class ClienteCard(QFrame):

    clicado = Signal(dict)

    def __init__(self, cliente, saldo_fiado, total_compras):

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
        layout.setSpacing(10)

        topo = QHBoxLayout()
        topo.setSpacing(12)

        avatar = Avatar(cliente.get("nome", ""), tamanho=44)

        col_nome = QVBoxLayout()
        col_nome.setSpacing(2)

        linha_nome = QHBoxLayout()

        nome = QLabel(cliente.get("nome") or "")
        nome.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tokens.TAMANHO_MD}px; font-weight:700; color:{tokens.TEXTO};
        """)

        ativo = cliente.get("ativo", True)

        badge = Badge("Ativo" if ativo else "Inativo", "sucesso" if ativo else "erro")

        linha_nome.addWidget(nome)
        linha_nome.addStretch()
        linha_nome.addWidget(badge)

        contato = " · ".join(
            filter(None, [cliente.get("telefone")])
        ) or "Sem telefone"

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

        layout.addLayout(topo)

        linha = QFrame()
        linha.setFixedHeight(1)
        linha.setStyleSheet(f"background:{tokens.BORDA}; border:none;")

        layout.addWidget(linha)

        rodape = QHBoxLayout()

        if saldo_fiado > 0:
            lbl_fiado = QLabel(f"Fiado: R$ {saldo_fiado:.2f}")
            lbl_fiado.setStyleSheet(f"""
                background:transparent; border:none;
                font-size:{tokens.TAMANHO_SM}px; font-weight:700; color:{tokens.ERRO};
            """)
            rodape.addWidget(lbl_fiado)

        rodape.addStretch()

        col_compras = QVBoxLayout()
        col_compras.setSpacing(0)

        lbl_compras_titulo = QLabel("TOTAL COMPRAS")
        lbl_compras_titulo.setAlignment(Qt.AlignRight)
        lbl_compras_titulo.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tokens.TAMANHO_XS}px; font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        lbl_compras_valor = QLabel(f"R$ {total_compras:.2f}")
        lbl_compras_valor.setAlignment(Qt.AlignRight)
        lbl_compras_valor.setStyleSheet(f"""
            background:transparent; border:none;
            font-size:{tokens.TAMANHO_BASE}px; font-weight:700; color:{tokens.SECUNDARIA};
        """)

        col_compras.addWidget(lbl_compras_titulo)
        col_compras.addWidget(lbl_compras_valor)

        rodape.addLayout(col_compras)

        layout.addLayout(rodape)

    def mousePressEvent(self, event):
        self.clicado.emit(self.cliente)
        super().mousePressEvent(event)


class Clientes(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.clientes = []
        self.vendas_por_cliente = {}
        self.filtro_status = "TODOS"

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

        config = configuracoes()
        nome_loja = config.get("nome_loja") or "Vertex ERP"

        titulo = QLabel(nome_loja)
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel("LOJA OPERACIONAL")
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.SECUNDARIA_HOVER}; font-weight:700;
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        self.bt_exportar = BotaoSecundario("Exportar Planilha", icone_nome="download")
        self.bt_exportar.clicked.connect(self.exportar_em_breve)

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
        self.card_ativos = CardKPI("Ativos (Frequentes)", "check", tokens.SECUNDARIA)
        self.card_inativos = CardKPI("Inativos (Ausentes)", "alert-triangle", tokens.ALERTA)
        self.card_faturamento = CardKPI("Faturamento (Histórico)", "trending-up", tokens.PRIMARIA)
        self.card_a_receber = CardKPI("A Receber (Fiado em aberto)", "credit-card", tokens.ERRO)

        resumo_layout.addWidget(self.card_total, 0, 0)
        resumo_layout.addWidget(self.card_ativos, 0, 1)
        resumo_layout.addWidget(self.card_inativos, 0, 2)
        resumo_layout.addWidget(self.card_faturamento, 0, 3)
        resumo_layout.addWidget(self.card_a_receber, 0, 4)

        for coluna in range(5):
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

        for rotulo in ["TODOS", "ATIVO", "INATIVO"]:

            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setMinimumHeight(44)
            bt.setMinimumWidth(80)
            bt.clicked.connect(
                lambda checked, r=rotulo: self.selecionar_status(r)
            )

            self.botoes_status[rotulo] = bt
            barra.addWidget(bt)

        layout.addLayout(barra)

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

        for cliente in self.clientes:
            cliente["saldo_fiado"] = saldo_cliente(cliente["id"])

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

        self.atualizar_cards_resumo()

        self.filtrar_clientes()

    # ==========================================
    # CARDS DE RESUMO
    # ==========================================

    def atualizar_cards_resumo(self):

        total = len(self.clientes)

        ativos = sum(
            1 for c in self.clientes if c.get("ativo", True)
        )

        inativos = total - ativos

        faturamento_total = sum(self.vendas_por_cliente.values())

        total_a_receber = sum(
            float(c.get("saldo_fiado", 0) or 0) for c in self.clientes
        )

        self.card_total.definir_valor(str(total))
        self.card_ativos.definir_valor(str(ativos))
        self.card_inativos.definir_valor(str(inativos))
        self.card_faturamento.definir_valor(f"R$ {faturamento_total:.2f}")
        self.card_a_receber.definir_valor(f"R$ {total_a_receber:.2f}")

    # ==========================================
    # FILTRO DE STATUS
    # ==========================================

    def selecionar_status(self, rotulo):

        self.filtro_status = rotulo

        for chave, botao in self.botoes_status.items():

            selecionado = chave == rotulo

            botao.setChecked(selecionado)

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.PRIMARIA if selecionado else tokens.CARD};
                    color: {"white" if selecionado else tokens.TEXTO};
                    border-radius: {tokens.RADIUS_SM}px;
                    border: 1px solid {tokens.PRIMARIA if selecionado else tokens.BORDA};
                    font-weight: 700;
                    font-size: {tokens.TAMANHO_SM}px;
                }}
                QPushButton:hover {{
                    background: {tokens.PRIMARIA_HOVER if selecionado else tokens.FUNDO};
                }}
            """)

        self.filtrar_clientes()

    # ==========================================
    # FILTRAR CLIENTES
    # ==========================================

    def filtrar_clientes(self):

        texto = self.pesquisa.text().lower().strip()

        clientes = self.clientes

        if self.filtro_status == "ATIVO":
            clientes = [c for c in clientes if c.get("ativo", True)]
        elif self.filtro_status == "INATIVO":
            clientes = [
                c for c in clientes if not c.get("ativo", True)
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

        self.preencher_grid(clientes)

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

            card = ClienteCard(
                cliente,
                cliente.get("saldo_fiado", 0),
                self.vendas_por_cliente.get(cliente["id"], 0),
            )
            card.clicado.connect(self.ver_ficha)

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

    def exportar_em_breve(self):
        QMessageBox.information(
            self,
            "Em breve",
            "A exportação de planilha ainda está em desenvolvimento.",
        )
