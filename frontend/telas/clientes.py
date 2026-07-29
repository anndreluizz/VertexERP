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
    QLineEdit,
    QFrame,
    QScrollArea,
    QDialog,
)


class StatCard(QFrame):

    def __init__(self, icone, cor, titulo, subtitulo, valor="0"):

        super().__init__()

        self.setStyleSheet("""
            QFrame {
                background:white;
                border-radius:12px;
                border:1px solid #eeeeee;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(2)

        topo = QHBoxLayout()

        # Qt espera cor em formato #AARRGGBB (alpha primeiro), entao
        # o alpha eh montado como prefixo, nao sufixo, do hex base
        cor_hex = cor.lstrip("#")

        lbl_icone = QLabel(icone)
        lbl_icone.setFixedSize(38, 38)
        lbl_icone.setAlignment(Qt.AlignCenter)
        lbl_icone.setStyleSheet(f"""
            background:#22{cor_hex};
            color:{cor};
            border-radius:19px;
            font-size:16px;
            border:none;
        """)

        traco = QLabel()
        traco.setFixedSize(28, 4)
        traco.setStyleSheet(f"""
            background:#55{cor_hex};
            border-radius:2px;
            border:none;
        """)

        topo.addWidget(lbl_icone)
        topo.addStretch()
        topo.addWidget(traco)

        layout.addLayout(topo)
        layout.addSpacing(10)

        self.lbl_valor = QLabel(str(valor))
        self.lbl_valor.setStyleSheet(
            "background:transparent; border:none; font-size:26px; "
            "font-weight:bold; color:#202225;"
        )

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(
            "background:transparent; border:none; font-size:11px; "
            "font-weight:bold; color:#202225;"
        )

        lbl_subtitulo = QLabel(subtitulo)
        lbl_subtitulo.setStyleSheet(
            "background:transparent; border:none; font-size:10px; "
            "color:#9E9E9E;"
        )

        rodape = QHBoxLayout()
        rodape.setSpacing(6)
        rodape.addWidget(lbl_titulo)
        rodape.addWidget(lbl_subtitulo)
        rodape.addStretch()

        layout.addWidget(self.lbl_valor)
        layout.addLayout(rodape)

    def atualizar(self, valor):
        self.lbl_valor.setText(str(valor))


class ClienteCard(QFrame):

    clicado = Signal(dict)

    def __init__(self, cliente, saldo_fiado, total_compras):

        super().__init__()

        self.cliente = cliente

        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                background:white;
                border-radius:12px;
                border:1px solid #eeeeee;
            }
            QFrame:hover {
                border:1px solid #90caf9;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        topo = QHBoxLayout()
        topo.setSpacing(12)

        avatar = QLabel(self._iniciais(cliente.get("nome", "")))
        avatar.setFixedSize(44, 44)
        avatar.setAlignment(Qt.AlignCenter)
        avatar.setStyleSheet("""
            background:#E3F2FD;
            color:#1565C0;
            border-radius:22px;
            font-weight:bold;
            font-size:14px;
            border:none;
        """)

        col_nome = QVBoxLayout()
        col_nome.setSpacing(2)

        linha_nome = QHBoxLayout()

        nome = QLabel(cliente.get("nome") or "")
        nome.setStyleSheet(
            "background:transparent; border:none; font-size:14px; "
            "font-weight:bold; color:#202225;"
        )

        ativo = cliente.get("ativo", True)

        badge = QLabel("Ativo" if ativo else "Inativo")
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"""
            background:{"#E8F5E9" if ativo else "#FFEBEE"};
            color:{"#2E7D32" if ativo else "#C62828"};
            border-radius:9px;
            font-size:10px;
            font-weight:bold;
            padding:2px 10px;
            border:none;
        """)

        linha_nome.addWidget(nome)
        linha_nome.addStretch()
        linha_nome.addWidget(badge)

        contato = " · ".join(
            filter(None, [cliente.get("telefone")])
        ) or "Sem telefone"

        lbl_contato = QLabel(f"📞 {contato}")
        lbl_contato.setStyleSheet(
            "background:transparent; border:none; font-size:11px; "
            "color:#757575;"
        )

        local = cliente.get("cidade") or cliente.get("endereco") or ""

        col_nome.addLayout(linha_nome)
        col_nome.addWidget(lbl_contato)

        if local:
            lbl_local = QLabel(f"📍 {local}")
            lbl_local.setStyleSheet(
                "background:transparent; border:none; font-size:11px; "
                "color:#757575;"
            )
            col_nome.addWidget(lbl_local)

        topo.addWidget(avatar)
        topo.addLayout(col_nome, stretch=1)

        layout.addLayout(topo)

        linha = QFrame()
        linha.setFixedHeight(1)
        linha.setStyleSheet("background:#f0f0f0; border:none;")

        layout.addWidget(linha)

        rodape = QHBoxLayout()

        if saldo_fiado > 0:
            lbl_fiado = QLabel(f"Fiado: R$ {saldo_fiado:.2f}")
            lbl_fiado.setStyleSheet(
                "background:transparent; border:none; font-size:11px; "
                "font-weight:bold; color:#C62828;"
            )
            rodape.addWidget(lbl_fiado)

        rodape.addStretch()

        col_compras = QVBoxLayout()
        col_compras.setSpacing(0)

        lbl_compras_titulo = QLabel("TOTAL COMPRAS")
        lbl_compras_titulo.setAlignment(Qt.AlignRight)
        lbl_compras_titulo.setStyleSheet(
            "background:transparent; border:none; font-size:9px; "
            "font-weight:bold; color:#9E9E9E;"
        )

        lbl_compras_valor = QLabel(f"R$ {total_compras:.2f}")
        lbl_compras_valor.setAlignment(Qt.AlignRight)
        lbl_compras_valor.setStyleSheet(
            "background:transparent; border:none; font-size:13px; "
            "font-weight:bold; color:#2E7D32;"
        )

        col_compras.addWidget(lbl_compras_titulo)
        col_compras.addWidget(lbl_compras_valor)

        rodape.addLayout(col_compras)

        layout.addLayout(rodape)

    @staticmethod
    def _iniciais(nome):

        partes = nome.strip().split()

        if not partes:
            return "?"

        if len(partes) == 1:
            return partes[0][:2].upper()

        return (partes[0][0] + partes[-1][0]).upper()

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

        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background:#f4f5f7;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(12)

        self.bt_voltar = QPushButton("‹ Voltar")
        self.bt_voltar.setStyleSheet("""
            QPushButton {
                background:transparent;
                color:gray;
                border:none;
                font-size:13px;
                font-weight:bold;
            }
            QPushButton:hover {
                color:#202225;
            }
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        icone_titulo = QLabel("👥")
        icone_titulo.setFixedSize(36, 36)
        icone_titulo.setAlignment(Qt.AlignCenter)
        icone_titulo.setStyleSheet("""
            background:#eef0f3;
            border-radius:8px;
            font-size:16px;
        """)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        config = configuracoes()
        nome_loja = config.get("nome_loja") or "Vertex ERP"

        titulo = QLabel(nome_loja)
        titulo.setStyleSheet(
            "background:transparent; font-size:16px; "
            "font-weight:bold; color:#202225;"
        )

        subtitulo = QLabel("LOJA OPERACIONAL")
        subtitulo.setStyleSheet(
            "background:transparent; font-size:10px; "
            "color:#2E7D32; font-weight:bold;"
        )

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        self.bt_tema = QPushButton("🌙")
        self.bt_tema.setFixedSize(38, 38)
        self.bt_tema.setStyleSheet("""
            QPushButton {
                background:#f4f5f7;
                border-radius:19px;
                font-size:14px;
            }
            QPushButton:hover {
                background:#e8e8e8;
            }
        """)
        self.bt_tema.clicked.connect(self.tema_em_breve)

        self.bt_exportar = QPushButton("⬇  Exportar Planilha")
        self.bt_exportar.setMinimumHeight(38)
        self.bt_exportar.setStyleSheet("""
            QPushButton {
                background:#f4f5f7;
                color:#202225;
                border-radius:10px;
                padding:0 16px;
                font-weight:bold;
                font-size:12px;
            }
            QPushButton:hover {
                background:#e8e8e8;
            }
        """)
        self.bt_exportar.clicked.connect(self.exportar_em_breve)

        self.bt_novo = QPushButton("+  Novo Cliente")
        self.bt_novo.setMinimumHeight(38)
        self.bt_novo.setStyleSheet("""
            QPushButton {
                background:#1565C0;
                color:white;
                border-radius:10px;
                padding:0 18px;
                font-weight:bold;
                font-size:12px;
            }
            QPushButton:hover {
                background:#0D47A1;
            }
        """)
        self.bt_novo.clicked.connect(self.novo_cliente)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addWidget(icone_titulo)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(self.bt_tema)
        cabecalho.addWidget(self.bt_exportar)
        cabecalho.addWidget(self.bt_novo)

        layout.addLayout(cabecalho)

        # ======================
        # CARDS DE RESUMO
        # ======================

        resumo_layout = QGridLayout()
        resumo_layout.setSpacing(12)

        self.card_total = StatCard(
            "👥", "#1565C0", "CADASTROS", "Total"
        )
        self.card_ativos = StatCard(
            "✓", "#2E7D32", "ATIVOS", "Frequentes"
        )
        self.card_inativos = StatCard(
            "⚠", "#F9A825", "INATIVOS", "Ausentes"
        )
        self.card_faturamento = StatCard(
            "📈", "#7B1FA2", "FATURAMENTO", "Histórico", "R$ 0,00"
        )

        resumo_layout.addWidget(self.card_total, 0, 0)
        resumo_layout.addWidget(self.card_ativos, 0, 1)
        resumo_layout.addWidget(self.card_inativos, 0, 2)
        resumo_layout.addWidget(self.card_faturamento, 0, 3)

        layout.addLayout(resumo_layout)

        # ======================
        # BUSCA + FILTRO
        # ======================

        barra = QHBoxLayout()
        barra.setSpacing(10)

        barra_frame = QFrame()
        barra_frame.setStyleSheet("""
            QFrame {
                background:white;
                border-radius:22px;
                border:1px solid #e0e0e0;
            }
        """)
        barra_frame_layout = QHBoxLayout(barra_frame)
        barra_frame_layout.setContentsMargins(16, 0, 16, 0)

        self.pesquisa = QLineEdit()
        self.pesquisa.setPlaceholderText(
            "Buscar por nome, telefone ou CPF/CNPJ..."
        )
        self.pesquisa.setMinimumHeight(44)
        self.pesquisa.setStyleSheet("""
            QLineEdit {
                border: none;
                font-size: 13px;
                color: #202225;
                background: transparent;
            }
        """)
        self.pesquisa.textChanged.connect(self.filtrar_clientes)

        barra_frame_layout.addWidget(self.pesquisa)

        barra.addWidget(barra_frame, stretch=1)

        self.botoes_status = {}

        for rotulo in ["TODOS", "ATIVO", "INATIVO"]:

            bt = QPushButton(rotulo)
            bt.setCheckable(True)
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
            "Clique em \"+ Novo Cliente\" pra começar o caderninho."
        )
        self.lbl_vazio.setAlignment(Qt.AlignCenter)
        self.lbl_vazio.setStyleSheet(
            "background:transparent; color:gray; font-size:13px;"
        )
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

        self.card_total.atualizar(str(total))
        self.card_ativos.atualizar(str(ativos))
        self.card_inativos.atualizar(str(inativos))
        self.card_faturamento.atualizar(
            f"R$ {faturamento_total:.2f}"
        )

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
                    background: {"#1565C0" if selecionado else "white"};
                    color: {"white" if selecionado else "#202225"};
                    border-radius: 10px;
                    border: 1px solid {"#1565C0" if selecionado else "#e0e0e0"};
                    font-weight: bold;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background: {"#0D47A1" if selecionado else "#f4f5f7"};
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

    def tema_em_breve(self):
        QMessageBox.information(
            self,
            "Em breve",
            "O modo escuro ainda está em desenvolvimento.",
        )

    def exportar_em_breve(self):
        QMessageBox.information(
            self,
            "Em breve",
            "A exportação de planilha ainda está em desenvolvimento.",
        )
