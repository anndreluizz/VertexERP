from datetime import datetime, timedelta

from telas.pagamento import PagamentoWindow
from telas.buscar_produto import BuscarProdutoDialog
from telas.venda_concluida import VendaConcluidaDialog
from telas.cadastro_produto import CadastroProdutoWindow
from telas.selecionar_cliente import SelecionarClienteDialog
from services.venda_service import finalizar_venda as enviar_venda
from services.produto_service import listar_produtos, cadastrar_produto
from services.pdv_service import buscar_produto
from services.caixa_service import caixa_aberto
from services.relatorio_service import relatorio_vendas
from services.api import configuracoes, me
from services import preferencias_service

ATALHOS_PADRAO = {"busca": "F1", "cadastro_rapido": "F4", "cancelar": "Esc"}

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QShortcut, QKeySequence, QFont, QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QFileDialog,
)

from design import tokens
from design.animations import fade_in
from design.icons import icone, icone_pixmap
from design.widgets import (
    Badge,
    BotaoPerigo,
    BotaoPrimario,
    BotaoSecundario,
    BotaoSucesso,
    CampoTexto,
)
from utils.formatacao import formatar_moeda

LARGURA_PAINEL_RESUMO = 340


def _parse_data(texto):
    try:
        return datetime.fromisoformat(texto)
    except (ValueError, TypeError):
        return None


def _parse_valor(texto):
    try:
        return max(0.0, float((texto or "").strip().replace(",", ".") or 0))
    except ValueError:
        return 0.0


class VendasSuspensasDialog(QDialog):
    """Lista as vendas suspensas do carrinho atual (só em memória — não
    sobrevivem a fechar o app, apenas a navegar entre telas, já que o
    PDV nunca é recriado enquanto o app está aberto). Permite retomar
    ou excluir uma venda suspensa."""

    def __init__(self, vendas_suspensas, parent=None):

        super().__init__(parent)

        self.indice_selecionado = None
        self.acao = None

        self.setWindowTitle("Vendas Suspensas")
        self.resize(480, 420)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        titulo = QLabel("Vendas Suspensas")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)
        layout.addWidget(titulo)

        self.lista = QTableWidget()
        self.lista.setColumnCount(1)
        self.lista.horizontalHeader().setVisible(False)
        self.lista.verticalHeader().setVisible(False)
        self.lista.setSelectionBehavior(QTableWidget.SelectRows)
        self.lista.setSelectionMode(QTableWidget.SingleSelection)
        self.lista.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lista.horizontalHeader().setStretchLastSection(True)
        self.lista.setStyleSheet(f"""
            QTableWidget {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                background:{tokens.CARD};
            }}
        """)

        self.lista.setRowCount(len(vendas_suspensas))

        for linha, venda in enumerate(vendas_suspensas):

            total = sum(
                item["preco"] * item["quantidade"] for item in venda["itens"]
            )
            hora_texto = venda["hora"].strftime("%H:%M")
            texto = (
                f"{venda['rotulo']}   ·   {len(venda['itens'])} item(ns)   ·   "
                f"{formatar_moeda(total)}   ·   {hora_texto}"
            )

            self.lista.setItem(linha, 0, QTableWidgetItem(texto))

        self.lista.verticalHeader().setDefaultSectionSize(40)

        if self.lista.rowCount() > 0:
            self.lista.selectRow(0)

        layout.addWidget(self.lista, stretch=1)

        rodape = QHBoxLayout()
        rodape.setSpacing(10)

        bt_excluir = BotaoPerigo("Excluir")
        bt_excluir.clicked.connect(self._excluir)

        bt_retomar = BotaoPrimario("Retomar")
        bt_retomar.clicked.connect(self._retomar)

        rodape.addWidget(bt_excluir)
        rodape.addStretch()
        rodape.addWidget(bt_retomar)

        layout.addLayout(rodape)

    def _linha_atual(self):
        linhas = self.lista.selectionModel().selectedRows()
        return linhas[0].row() if linhas else -1

    def _retomar(self):
        linha = self._linha_atual()
        if linha < 0:
            return
        self.indice_selecionado = linha
        self.acao = "retomar"
        self.accept()

    def _excluir(self):
        linha = self._linha_atual()
        if linha < 0:
            return
        self.indice_selecionado = linha
        self.acao = "excluir"
        self.accept()


class PDV(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.itens = []
        self.cliente_id = None
        self.cliente_nome = None
        self.desconto_valor = 0.0
        self.acrescimo_valor = 0.0
        self.vendas_suspensas = []

        self._usuario_id = (me() or {}).get("id")
        self.atalhos = self._carregar_atalhos()

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Cabeçalho — largura plena, acima das duas colunas.
        layout.addLayout(self._construir_cabecalho())

        # ======================
        # CORPO: carrinho fica numa área que rola se a janela for
        # baixa demais (mesma solução já usada antes pra não estourar
        # em notebooks/1366x768) — o painel de resumo financeiro +
        # botão Pagar fica de fora da rolagem, sempre visível, à
        # direita.
        # ======================

        corpo = QHBoxLayout()
        corpo.setContentsMargins(24, 4, 24, 20)
        corpo.setSpacing(20)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        coluna_esquerda = QWidget()
        coluna_esquerda.setStyleSheet("background:transparent;")

        layout_esquerda = QVBoxLayout(coluna_esquerda)
        layout_esquerda.setContentsMargins(0, 0, 4, 0)
        layout_esquerda.setSpacing(12)

        layout_esquerda.addWidget(self._construir_campo_codigo())
        layout_esquerda.addWidget(self.lbl_status_busca)
        layout_esquerda.addLayout(self._construir_acoes_rapidas())
        layout_esquerda.addWidget(self._construir_linha_cliente())
        layout_esquerda.addWidget(self._construir_mais_vendidos())
        layout_esquerda.addWidget(self._construir_cartao_tabela(), stretch=1)

        self.tabela.setMinimumHeight(160)

        scroll.setWidget(coluna_esquerda)
        corpo.addWidget(scroll, stretch=1)

        painel_resumo = QWidget()
        painel_resumo.setFixedWidth(LARGURA_PAINEL_RESUMO)
        painel_resumo.setStyleSheet("background:transparent;")

        layout_resumo = QVBoxLayout(painel_resumo)
        layout_resumo.setContentsMargins(0, 0, 0, 0)
        layout_resumo.setSpacing(12)

        # stretch=1 pro cartão de resumo acompanhar a altura do
        # carrinho ao lado, em vez de ficar pequeno com um vão cinza
        # vazio embaixo — o conteúdo continua compacto e ancorado no
        # topo do card (ver stretch interno em _construir_cartao_resumo).
        layout_resumo.addWidget(self._construir_cartao_resumo(), stretch=1)
        layout_resumo.addWidget(self._construir_botao_pagar())

        corpo.addWidget(painel_resumo)

        layout.addLayout(corpo, stretch=1)

        # ======================
        # ATALHOS DE TECLADO
        # ======================

        contexto = Qt.WidgetWithChildrenShortcut

        self.atalho_f1 = QShortcut(QKeySequence(self.atalhos["busca"]), self)
        self.atalho_f1.setContext(contexto)
        self.atalho_f1.activated.connect(self.abrir_busca)

        self.atalho_f4 = QShortcut(QKeySequence(self.atalhos["cadastro_rapido"]), self)
        self.atalho_f4.setContext(contexto)
        self.atalho_f4.activated.connect(self.abrir_novo_produto)

        self.atalho_esc = QShortcut(QKeySequence(self.atalhos["cancelar"]), self)
        self.atalho_esc.setContext(contexto)
        self.atalho_esc.activated.connect(self.cancelar_venda)

        # F2 (cliente) e F6 (desconto/acréscimo) não conflitam com
        # nenhum atalho existente e já têm uma ação óbvia associada —
        # F3 (pagar) continua tratado globalmente por PrincipalWindow.
        self.atalho_f2 = QShortcut(QKeySequence("F2"), self)
        self.atalho_f2.setContext(contexto)
        self.atalho_f2.activated.connect(self.abrir_selecionar_cliente)

        self.atalho_f6 = QShortcut(QKeySequence("F6"), self)
        self.atalho_f6.setContext(contexto)
        self.atalho_f6.activated.connect(self._alternar_bloco_ajuste)

        fade_in(self, duracao=200)

    def showEvent(self, event):
        super().showEvent(event)
        self.recarregar_atalhos()
        self.campo_codigo.setFocus()
        # as duas chamadas abaixo dependem do backend (rede) -- adiadas
        # pro próximo ciclo de eventos pra tela do PDV aparecer na hora
        # em vez de travar a troca de aba esperando a resposta.
        QTimer.singleShot(0, self.atualizar_indicador_caixa)
        QTimer.singleShot(0, self.atualizar_mais_vendidos)

    def _carregar_atalhos(self):
        salvo = preferencias_service.carregar(self._usuario_id, "pdv_atalhos", {})
        return {**ATALHOS_PADRAO, **(salvo or {})}

    def recarregar_atalhos(self):
        """Reflete na hora qualquer remapeamento feito em Configurações
        — chamado toda vez que a tela do PDV é reaberta, já que o
        widget nunca é recriado enquanto o app está de pé."""

        self.atalhos = self._carregar_atalhos()

        self.atalho_f1.setKey(QKeySequence(self.atalhos["busca"]))
        self.atalho_f4.setKey(QKeySequence(self.atalhos["cadastro_rapido"]))
        self.atalho_esc.setKey(QKeySequence(self.atalhos["cancelar"]))

        self.bt_buscar.setText(f"Buscar ({self.atalhos['busca']})")
        self.bt_adicionar.setText(f"Novo Produto ({self.atalhos['cadastro_rapido']})")

    # ==================================================
    # CONSTRUÇÃO DA INTERFACE
    # ==================================================

    def _construir_cabecalho(self):

        cabecalho = QHBoxLayout()
        cabecalho.setContentsMargins(24, 16, 24, 12)
        cabecalho.setSpacing(10)

        self.bt_voltar = QPushButton()
        self.bt_voltar.setFixedSize(38, 38)
        self.bt_voltar.setCursor(Qt.PointingHandCursor)
        self.bt_voltar.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
        self.bt_voltar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background: {tokens.FUNDO}; }}
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Frente de Caixa")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)

        config = configuracoes()
        nome_loja = config.get("nome_loja") or ""

        self.lbl_loja = QLabel(nome_loja)
        self.lbl_loja.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(self.lbl_loja)

        self.badge_caixa = Badge("Caixa aberto", "sucesso")

        self.bt_retomar = BotaoSecundario("Vendas Suspensas")
        self.bt_retomar.setEnabled(False)
        self.bt_retomar.clicked.connect(self.abrir_vendas_suspensas)

        self.bt_suspender = BotaoSecundario("Suspender")
        self.bt_suspender.clicked.connect(self.suspender_venda)

        self.bt_orcamento = BotaoSecundario("Orçamento", icone_nome="printer")
        self.bt_orcamento.clicked.connect(self.imprimir_orcamento)

        self.bt_cancelar = BotaoPerigo("Cancelar Venda", icone_nome="x")
        self.bt_cancelar.clicked.connect(self.cancelar_venda)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addLayout(col_titulo)
        cabecalho.addSpacing(4)
        cabecalho.addWidget(self.badge_caixa, alignment=Qt.AlignVCenter)
        cabecalho.addStretch()
        cabecalho.addWidget(self.bt_retomar)
        cabecalho.addWidget(self.bt_suspender)
        cabecalho.addWidget(self.bt_orcamento)
        cabecalho.addWidget(self.bt_cancelar)

        return cabecalho

    def _construir_campo_codigo(self):

        container = QFrame()
        container.setFixedHeight(64)
        container.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border: 2px solid {tokens.PRIMARIA};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(12)

        self.campo_codigo = QLineEdit()
        self.campo_codigo.setPlaceholderText(
            "Digite código, código de barras ou nome do produto..."
        )
        self.campo_codigo.setFont(QFont(tokens.FONTE_FAMILIA_PADRAO, 18))
        self.campo_codigo.setStyleSheet(f"""
            QLineEdit {{
                border: none; outline: none; background: transparent;
                color: {tokens.TEXTO}; font-size: 18px; font-weight: 600;
            }}
        """)
        # ícone desenhado dentro do próprio campo (QLineEdit.addAction)
        # em vez de um QLabel separado ao lado -- evita qualquer
        # contorno/moldura indesejada que um widget irmão poderia
        # ganhar do estilo do Qt quando o campo está focado.
        self.campo_codigo.addAction(
            icone("search", cor=tokens.PRIMARIA, tamanho=20),
            QLineEdit.LeadingPosition,
        )
        self.campo_codigo.returnPressed.connect(self.processar_codigo)
        layout.addWidget(self.campo_codigo, stretch=1)

        # "pílula" cinza discreta -- sem borda nenhuma, só pra não
        # sobrar o contorno de foco do Qt (outline) perto do texto
        # quando o campo de busca está com foco.
        dica = QLabel(f"{self.atalhos['busca']} busca por nome")
        dica.setStyleSheet(f"""
            background:{tokens.FUNDO}; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; border:none; outline:none;
            border-radius:{tokens.RADIUS_PILL}px; padding: 4px 12px;
        """)
        layout.addWidget(dica)

        self.lbl_status_busca = QLabel("")
        self.lbl_status_busca.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; padding-left: 4px;
        """)

        return container

    def _construir_acoes_rapidas(self):
        """[Buscar] e [Novo Produto] — formas alternativas de adicionar
        item ao carrinho, por isso ficam coladas no campo de código em
        vez de lá embaixo, longe de onde o operador está olhando."""

        linha = QHBoxLayout()
        linha.setSpacing(10)

        self.bt_buscar = BotaoSecundario(
            f"Buscar ({self.atalhos['busca']})", icone_nome="search"
        )
        self.bt_buscar.clicked.connect(self.abrir_busca)

        self.bt_adicionar = BotaoSecundario(
            f"Novo Produto ({self.atalhos['cadastro_rapido']})", icone_nome="plus"
        )
        self.bt_adicionar.clicked.connect(self.abrir_novo_produto)

        linha.addWidget(self.bt_buscar)
        linha.addWidget(self.bt_adicionar)
        linha.addStretch()

        return linha

    def _construir_linha_cliente(self):

        linha = QFrame()
        linha.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(10)

        lbl_icone = QLabel()
        lbl_icone.setStyleSheet("background:transparent;")
        lbl_icone.setPixmap(icone_pixmap("users", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        layout.addWidget(lbl_icone)

        col_cliente = QVBoxLayout()
        col_cliente.setSpacing(0)

        lbl_rotulo = QLabel("CLIENTE")
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        self.lbl_cliente = QLabel("Nenhum cliente selecionado")
        self.lbl_cliente.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)

        col_cliente.addWidget(lbl_rotulo)
        col_cliente.addWidget(self.lbl_cliente)

        layout.addLayout(col_cliente)
        layout.addStretch()

        self.bt_limpar_cliente = QPushButton("remover")
        self.bt_limpar_cliente.setCursor(Qt.PointingHandCursor)
        self.bt_limpar_cliente.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.ERRO}; font-size:{tokens.TAMANHO_XS}px;
            }}
        """)
        self.bt_limpar_cliente.clicked.connect(self.limpar_cliente)
        self.bt_limpar_cliente.setVisible(False)
        layout.addWidget(self.bt_limpar_cliente)

        self.bt_selecionar_cliente = BotaoSecundario(
            f"Selecionar (F2)", icone_nome="users"
        )
        self.bt_selecionar_cliente.setMinimumHeight(32)
        self.bt_selecionar_cliente.clicked.connect(self.abrir_selecionar_cliente)
        layout.addWidget(self.bt_selecionar_cliente)

        return linha

    def _construir_mais_vendidos(self):

        self.linha_mais_vendidos = QFrame()
        self.linha_mais_vendidos.setStyleSheet("background:transparent; border:none;")
        self.linha_mais_vendidos.setVisible(False)

        layout = QHBoxLayout(self.linha_mais_vendidos)
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(8)

        lbl_icone = QLabel()
        lbl_icone.setStyleSheet("background:transparent;")
        lbl_icone.setPixmap(icone_pixmap("trending-up", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        layout.addWidget(lbl_icone)

        lbl_titulo = QLabel("Mais vendidos:")
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(lbl_titulo)

        self.layout_chips_mais_vendidos = QHBoxLayout()
        self.layout_chips_mais_vendidos.setSpacing(6)
        layout.addLayout(self.layout_chips_mais_vendidos)

        layout.addStretch()

        return self.linha_mais_vendidos

    def atualizar_mais_vendidos(self):
        """Painel de acesso rápido pros produtos mais vendidos nos
        últimos 30 dias. Usa o relatório de vendas (top_produtos já vem
        agregado pelo banco) em vez de baixar o histórico de vendas
        inteiro pro cliente e somar em Python -- com muitas vendas
        registradas, aquele caminho antigo deixava a abertura do PDV
        visivelmente lenta."""

        while self.layout_chips_mais_vendidos.count():
            item = self.layout_chips_mais_vendidos.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        hoje = datetime.now().date()
        inicio = hoje - timedelta(days=30)

        try:
            relatorio = relatorio_vendas(
                inicio.isoformat(), hoje.isoformat(), limit=1
            )
            produtos = listar_produtos()
        except Exception:
            self.linha_mais_vendidos.setVisible(False)
            return

        produtos_por_nome = {p["nome"]: p for p in produtos}
        top = relatorio.get("top_produtos", [])[:5]
        exibidos = 0

        for entrada in top:

            produto = produtos_por_nome.get(entrada.get("produto"))

            if not produto or not produto.get("ativo", True):
                continue

            chip = BotaoSecundario(produto["nome"][:18])
            chip.setMinimumHeight(30)
            chip.clicked.connect(
                lambda _checked, p=produto: self.adicionar_produto_ao_carrinho(
                    {
                        "id": p["id"],
                        "codigo": p["codigo"],
                        "nome": p["nome"],
                        "preco": float(p["preco_venda"]),
                        "estoque": p["estoque"],
                    },
                    1,
                )
            )
            self.layout_chips_mais_vendidos.addWidget(chip)
            exibidos += 1

        self.linha_mais_vendidos.setVisible(exibidos > 0)

    def _construir_cartao_tabela(self):
        """A tabela em si (self.tabela) fica dentro de um Card, mas o
        atributo continua sendo o QTableWidget puro — atualizar_tabela()
        mexe direto nele (setRowCount/setItem/setCellWidget). Alterna
        com um estado vazio (self.pilha_carrinho) quando não há itens,
        pra não deixar um vão em branco atrás da tabela zerada."""

        cartao = QFrame()
        cartao.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        layout = QVBoxLayout(cartao)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        cabecalho_tabela = QHBoxLayout()
        cabecalho_tabela.setContentsMargins(16, 14, 16, 10)

        lbl_titulo_tabela = QLabel("PRODUTOS DA VENDA")
        lbl_titulo_tabela.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:800; letter-spacing: 0.5px;
        """)
        cabecalho_tabela.addWidget(lbl_titulo_tabela)
        cabecalho_tabela.addStretch()

        self.lbl_itens_tabela = QLabel("0 itens")
        self.lbl_itens_tabela.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        cabecalho_tabela.addWidget(self.lbl_itens_tabela)

        layout.addLayout(cabecalho_tabela)

        divisor_topo = QFrame()
        divisor_topo.setFixedHeight(1)
        divisor_topo.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        layout.addWidget(divisor_topo)

        self.pilha_carrinho = QStackedWidget()
        self.pilha_carrinho.setStyleSheet("background:transparent;")

        self.pilha_carrinho.addWidget(self._construir_estado_vazio_carrinho())

        self.tabela = QTableWidget()

        self.tabela.setColumnCount(6)

        self.tabela.setHorizontalHeaderLabels([
            "Código",
            "Produto",
            "Qtde",
            "Unitário",
            "Total",
            "",
        ])

        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setSelectionMode(QTableWidget.NoSelection)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setShowGrid(False)
        self.tabela.verticalHeader().setDefaultSectionSize(48)

        self.tabela.horizontalHeader().setStretchLastSection(False)
        self.tabela.setColumnWidth(2, 120)
        self.tabela.setColumnWidth(5, 48)
        self.tabela.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                border: none;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                font-size: {tokens.TAMANHO_BASE}px;
                alternate-background-color: {tokens.FUNDO};
            }}
            QHeaderView::section {{
                background: {tokens.CARD};
                color: {tokens.TEXTO_SECUNDARIO};
                font-weight: 700;
                font-size: {tokens.TAMANHO_XS}px;
                padding: 10px 8px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
            QTableWidget::item {{
                border-bottom: 1px solid {tokens.BORDA};
                padding: 4px;
            }}
        """)
        self.tabela.setAlternatingRowColors(True)

        self.pilha_carrinho.addWidget(self.tabela)
        self.pilha_carrinho.setCurrentIndex(0)

        layout.addWidget(self.pilha_carrinho, stretch=1)

        return cartao

    def _construir_estado_vazio_carrinho(self):

        estado = QWidget()
        estado.setStyleSheet("background:transparent;")

        layout = QVBoxLayout(estado)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)

        lbl_icone = QLabel()
        lbl_icone.setAlignment(Qt.AlignCenter)
        lbl_icone.setStyleSheet("background:transparent;")
        lbl_icone.setPixmap(
            icone_pixmap("shopping-cart", cor=tokens.TEXTO_TERCIARIO, tamanho=40)
        )
        layout.addWidget(lbl_icone)

        lbl_titulo = QLabel("Nenhum produto na venda")
        lbl_titulo.setAlignment(Qt.AlignCenter)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:700; margin-top: 6px;
        """)
        layout.addWidget(lbl_titulo)

        lbl_dica = QLabel(
            "Digite um código, leia um código de barras ou pressione "
            f"{self.atalhos['busca']} para buscar."
        )
        lbl_dica.setAlignment(Qt.AlignCenter)
        lbl_dica.setWordWrap(True)
        lbl_dica.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        lbl_dica.setMaximumWidth(340)
        layout.addWidget(lbl_dica, alignment=Qt.AlignCenter)

        return estado

    def _linha_resumo(self, rotulo):
        """Uma linha "rótulo ..... valor" do card de resumo — devolve o
        QLabel do valor pra poder atualizar depois."""

        linha = QHBoxLayout()
        linha.setSpacing(8)

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        lbl_valor = QLabel("R$ 0,00")
        lbl_valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)

        linha.addWidget(lbl_rotulo)
        linha.addStretch()
        linha.addWidget(lbl_valor)

        return linha, lbl_valor

    def _construir_cartao_resumo(self):

        cartao = QFrame()
        cartao.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_LG}px;
            }}
        """)

        layout = QVBoxLayout(cartao)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)

        titulo = QLabel("RESUMO DA VENDA")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800; letter-spacing: 0.5px;
        """)
        layout.addWidget(titulo)

        linha_itens, self.lbl_itens_valor = self._linha_resumo("Itens")
        self.lbl_itens_valor.setText("0")
        layout.addLayout(linha_itens)

        linha_subtotal, self.lbl_subtotal_valor = self._linha_resumo("Subtotal")
        layout.addLayout(linha_subtotal)

        # ------ desconto / acréscimo (recolhido por padrão) ------

        self.bt_alternar_ajuste = QPushButton("+ Desconto ou acréscimo (F6)")
        self.bt_alternar_ajuste.setCursor(Qt.PointingHandCursor)
        self.bt_alternar_ajuste.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; text-align:left;
                color:{tokens.PRIMARIA}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:600; padding: 2px 0;
            }}
        """)
        self.bt_alternar_ajuste.clicked.connect(self._alternar_bloco_ajuste)
        layout.addWidget(self.bt_alternar_ajuste)

        self.bloco_ajuste = QFrame()
        self.bloco_ajuste.setVisible(False)
        self.bloco_ajuste.setStyleSheet(f"""
            QFrame {{
                background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
            }}
        """)

        ajuste_layout = QHBoxLayout(self.bloco_ajuste)
        ajuste_layout.setContentsMargins(14, 12, 14, 12)
        ajuste_layout.setSpacing(12)

        col_desconto = QVBoxLayout()
        col_desconto.setSpacing(4)
        lbl_desconto = QLabel("DESCONTO (R$)")
        lbl_desconto.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)
        self.campo_desconto = CampoTexto("0,00")
        self.campo_desconto.textChanged.connect(self._recalcular_totais)
        col_desconto.addWidget(lbl_desconto)
        col_desconto.addWidget(self.campo_desconto)

        col_acrescimo = QVBoxLayout()
        col_acrescimo.setSpacing(4)
        lbl_acrescimo = QLabel("ACRÉSCIMO (R$)")
        lbl_acrescimo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)
        self.campo_acrescimo = CampoTexto("0,00")
        self.campo_acrescimo.textChanged.connect(self._recalcular_totais)
        col_acrescimo.addWidget(lbl_acrescimo)
        col_acrescimo.addWidget(self.campo_acrescimo)

        ajuste_layout.addLayout(col_desconto)
        ajuste_layout.addLayout(col_acrescimo)

        layout.addWidget(self.bloco_ajuste)

        linha_desconto, self.lbl_desconto_valor = self._linha_resumo("Desconto")
        layout.addLayout(linha_desconto)

        linha_acrescimo, self.lbl_acrescimo_valor = self._linha_resumo("Acréscimo")
        layout.addLayout(linha_acrescimo)

        divisor = QFrame()
        divisor.setFixedHeight(1)
        divisor.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        layout.addWidget(divisor)

        lbl_total_rotulo = QLabel("TOTAL")
        lbl_total_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800; letter-spacing: 0.5px;
        """)
        layout.addWidget(lbl_total_rotulo)

        self.total = QLabel("R$ 0,00")
        self.total.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.total.setStyleSheet(f"""
            background:transparent; font-size: 34px; font-weight: 800;
            color: {tokens.SECUNDARIA};
        """)
        layout.addWidget(self.total)

        # o card acompanha a altura do carrinho ao lado (ver stretch=1
        # em __init__) — o conteúdo fica ancorado no topo, o resto do
        # espaço é preenchido aqui dentro, sem sobrar vão cinza embaixo.
        layout.addStretch()

        return cartao

    def _construir_botao_pagar(self):

        self.bt_pagar = BotaoSucesso("Pagar (F3)", icone_nome="credit-card")
        self.bt_pagar.setMinimumHeight(58)
        self.bt_pagar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.bt_pagar.clicked.connect(self.finalizar_venda)

        return self.bt_pagar

    # ==================================================
    # INDICADOR DE CAIXA ABERTO
    # ==================================================

    def atualizar_indicador_caixa(self):

        info = caixa_aberto()

        if not info:
            self.badge_caixa.setText("Caixa fechado")
            self.badge_caixa.setStyleSheet(f"""
                background: {tokens.ERRO_CLARO}; color: {tokens.ERRO_HOVER};
                border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
                font-weight: 600; padding: 3px 10px;
            """)
            return

        abertura = _parse_data(info.get("data_abertura"))
        hora_texto = abertura.strftime("%H:%M") if abertura else "—"

        self.badge_caixa.setText(f"Caixa aberto às {hora_texto}")
        self.badge_caixa.setStyleSheet(f"""
            background: {tokens.SUCESSO_CLARO}; color: {tokens.SECUNDARIA_HOVER};
            border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
            font-weight: 600; padding: 3px 10px;
        """)

    # ==================================================
    # CÓDIGO DE BARRAS (campo gigante)
    # ==================================================

    def processar_codigo(self):

        codigo = self.campo_codigo.text().strip()

        if not codigo:
            return

        produto = buscar_produto(codigo)

        if produto is None:
            self._mostrar_status_busca(f"Produto não encontrado: {codigo}", erro=True)
            self.campo_codigo.selectAll()
            return

        self.adicionar_produto_ao_carrinho(produto, 1)
        self.campo_codigo.clear()
        self._mostrar_status_busca(f"Adicionado: {produto['nome']}", erro=False)

    def _mostrar_status_busca(self, texto, erro):

        cor = tokens.ERRO if erro else tokens.SECUNDARIA
        self.lbl_status_busca.setStyleSheet(f"""
            background:transparent; color:{cor};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        self.lbl_status_busca.setText(texto)

        QTimer.singleShot(
            2500,
            lambda: (
                self.lbl_status_busca.setText("")
                if self.lbl_status_busca.text() == texto else None
            ),
        )

    # ==================================================
    # BUSCAR PRODUTO (F1) - abre o modal de pesquisa
    # ==================================================

    def abrir_busca(self):

        dialog = BuscarProdutoDialog(self)
        dialog.produto_selecionado.connect(
            self.adicionar_produto_ao_carrinho
        )
        dialog.exec()

    def adicionar_produto_ao_carrinho(self, produto, quantidade):

        item_existente = next(
            (item for item in self.itens if item["id"] == produto["id"]),
            None,
        )

        no_carrinho = item_existente["quantidade"] if item_existente else 0
        estoque = produto.get("estoque")

        # estoque None = dado nao veio junto (nao deveria acontecer,
        # mas nao trava a venda por causa disso - so pula a checagem)
        if estoque is not None and no_carrinho + quantidade > estoque:

            if estoque <= 0:
                mensagem = f"{produto['nome']} está sem estoque disponível."
            elif no_carrinho > 0:
                mensagem = (
                    f"Estoque insuficiente de {produto['nome']} — "
                    f"disponível: {estoque}, já no carrinho: {no_carrinho}."
                )
            else:
                mensagem = (
                    f"Estoque insuficiente de {produto['nome']} — "
                    f"disponível: {estoque}."
                )

            self._mostrar_status_busca(mensagem, erro=True)
            return

        if item_existente:
            item_existente["quantidade"] += quantidade
        else:
            self.itens.append(
                {
                    "id": produto["id"],
                    "codigo": produto["codigo"],
                    "nome": produto["nome"],
                    "preco": float(produto["preco"]),
                    "quantidade": quantidade,
                    "estoque": estoque,
                }
            )

        self.atualizar_tabela()

    # ==================================================
    # NOVO PRODUTO (F4) - cadastro completo sem sair do PDV
    # ==================================================

    def abrir_novo_produto(self):

        dialog = CadastroProdutoWindow()

        if dialog.exec() != QDialog.Accepted:
            return

        response = cadastrar_produto(dialog.dados)

        if response.status_code != 201:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
            return

        produto_criado = response.json()

        # a resposta do cadastro vem no formato "cru" (preco_venda) --
        # o carrinho espera o formato do PDV (preco), entao rebusca
        # pelo codigo pra pegar exatamente o mesmo shape que o F1/scanner usa
        codigo = (
            produto_criado.get("codigo_barras")
            or produto_criado.get("codigo")
        )

        produto = buscar_produto(codigo)

        if produto is None:
            return

        self.adicionar_produto_ao_carrinho(produto, 1)
        self._mostrar_status_busca(
            f"Produto cadastrado e adicionado: {produto['nome']}",
            erro=False,
        )

    # ==================================================
    # CLIENTE (opcional, vale pra qualquer forma de pagamento)
    # ==================================================

    def abrir_selecionar_cliente(self):

        dialogo = SelecionarClienteDialog(self)
        dialogo.cliente_selecionado.connect(self.definir_cliente)
        dialogo.exec()

    def definir_cliente(self, cliente):

        self.cliente_id = cliente["id"]
        self.cliente_nome = cliente["nome"]

        self.lbl_cliente.setText(cliente["nome"])
        self.lbl_cliente.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        self.bt_limpar_cliente.setVisible(True)

    def limpar_cliente(self):

        self.cliente_id = None
        self.cliente_nome = None

        self.lbl_cliente.setText("Nenhum cliente selecionado")
        self.lbl_cliente.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        self.bt_limpar_cliente.setVisible(False)

    # ==================================================
    # DESCONTO / ACRÉSCIMO
    # ==================================================

    def _alternar_bloco_ajuste(self):
        self.bloco_ajuste.setVisible(not self.bloco_ajuste.isVisible())

    # ==================================================
    # ATUALIZAR TABELA / TOTAIS
    # ==================================================

    def atualizar_tabela(self):

        self.tabela.setRowCount(len(self.itens))

        for linha, item in enumerate(self.itens):
            subtotal = item["preco"] * item["quantidade"]

            self.tabela.setItem(
                linha, 0, QTableWidgetItem(item["codigo"])
            )

            item_nome = QTableWidgetItem(item["nome"])
            item_nome.setFont(QFont(tokens.FONTE_FAMILIA_PADRAO, tokens.TAMANHO_MD, QFont.DemiBold))
            self.tabela.setItem(linha, 1, item_nome)

            self.tabela.setCellWidget(
                linha, 2, self.criar_widget_qtde(linha, item["quantidade"])
            )

            self.tabela.setItem(
                linha, 3, QTableWidgetItem(formatar_moeda(item["preco"]))
            )

            self.tabela.setItem(
                linha, 4, QTableWidgetItem(formatar_moeda(subtotal))
            )

            self.tabela.setCellWidget(
                linha, 5, self.criar_widget_excluir(linha)
            )

        self.pilha_carrinho.setCurrentWidget(
            self.tabela if self.itens else self.pilha_carrinho.widget(0)
        )

        self._recalcular_totais()
        self.campo_codigo.setFocus()

    def _recalcular_totais(self):

        subtotal = sum(item["preco"] * item["quantidade"] for item in self.itens)

        self.desconto_valor = _parse_valor(self.campo_desconto.text())
        self.acrescimo_valor = _parse_valor(self.campo_acrescimo.text())

        total = max(0.0, subtotal - self.desconto_valor + self.acrescimo_valor)

        self.lbl_itens_valor.setText(str(len(self.itens)))
        self.lbl_itens_tabela.setText(
            "1 item" if len(self.itens) == 1 else f"{len(self.itens)} itens"
        )
        self.lbl_subtotal_valor.setText(formatar_moeda(subtotal))

        self.lbl_desconto_valor.setText(
            f"- {formatar_moeda(self.desconto_valor)}"
            if self.desconto_valor else formatar_moeda(0)
        )
        self.lbl_desconto_valor.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            color: {tokens.ERRO if self.desconto_valor else tokens.TEXTO};
        """)

        self.lbl_acrescimo_valor.setText(
            f"+ {formatar_moeda(self.acrescimo_valor)}"
            if self.acrescimo_valor else formatar_moeda(0)
        )
        self.lbl_acrescimo_valor.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            color: {tokens.SECUNDARIA if self.acrescimo_valor else tokens.TEXTO};
        """)

        self.total.setText(formatar_moeda(total))

        return total

    # ==================================================
    # WIDGETS DE QUANTIDADE / EXCLUIR (por linha)
    # ==================================================

    def criar_widget_qtde(self, linha, quantidade):

        widget = QWidget()

        caixa = QHBoxLayout(widget)
        caixa.setContentsMargins(4, 2, 4, 2)
        caixa.setSpacing(4)

        estilo_botao = f"""
            QPushButton {{
                background:{tokens.FUNDO};
                border-radius:4px;
                font-weight:bold;
                color:{tokens.TEXTO};
            }}
            QPushButton:hover {{
                background:{tokens.BORDA};
            }}
        """

        bt_menos = QPushButton("-")
        bt_menos.setFixedSize(24, 24)
        bt_menos.setCursor(Qt.PointingHandCursor)
        bt_menos.setStyleSheet(estilo_botao)
        bt_menos.clicked.connect(
            lambda: self.alterar_quantidade(linha, -1)
        )

        lbl_qtde = QLabel(str(quantidade))
        lbl_qtde.setAlignment(Qt.AlignCenter)
        lbl_qtde.setFixedWidth(24)
        lbl_qtde.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO}; font-weight:bold;"
        )

        bt_mais = QPushButton("+")
        bt_mais.setFixedSize(24, 24)
        bt_mais.setCursor(Qt.PointingHandCursor)
        bt_mais.setStyleSheet(estilo_botao)
        bt_mais.clicked.connect(
            lambda: self.alterar_quantidade(linha, 1)
        )

        caixa.addWidget(bt_menos)
        caixa.addWidget(lbl_qtde)
        caixa.addWidget(bt_mais)
        caixa.addStretch()

        return widget

    def criar_widget_excluir(self, linha):

        widget = QWidget()

        caixa = QHBoxLayout(widget)
        caixa.setContentsMargins(0, 0, 0, 0)

        bt_excluir = QPushButton()
        bt_excluir.setFixedSize(28, 28)
        bt_excluir.setCursor(Qt.PointingHandCursor)
        bt_excluir.setIcon(icone("trash-2", cor=tokens.TEXTO_TERCIARIO, tamanho=15))
        bt_excluir.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                border:none;
                border-radius:6px;
            }}
            QPushButton:hover {{
                background:{tokens.ERRO_CLARO};
            }}
        """)
        bt_excluir.clicked.connect(
            lambda: self.remover_item(linha)
        )

        caixa.addWidget(bt_excluir)

        return widget

    def alterar_quantidade(self, linha, delta):

        if linha >= len(self.itens):
            return

        item = self.itens[linha]
        nova_quantidade = item["quantidade"] + delta

        if nova_quantidade <= 0:
            self.remover_item(linha)
            return

        estoque = item.get("estoque")

        if delta > 0 and estoque is not None and nova_quantidade > estoque:
            self._mostrar_status_busca(
                f"Estoque insuficiente de {item['nome']} — "
                f"disponível: {estoque}.",
                erro=True,
            )
            return

        item["quantidade"] = nova_quantidade

        self.atualizar_tabela()

    def remover_item(self, linha):

        if linha >= len(self.itens):
            return

        del self.itens[linha]

        self.atualizar_tabela()

    # ==================================================
    # CANCELAR VENDA
    # ==================================================

    def cancelar_venda(self):

        if not self.itens:
            return

        resposta = QMessageBox.question(
            self,
            "Cancelar Venda",
            "Deseja cancelar esta venda?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if resposta == QMessageBox.No:
            return

        self.limpar_venda()

    def limpar_venda(self):

        self.itens.clear()

        self.tabela.setRowCount(0)
        self.pilha_carrinho.setCurrentWidget(self.pilha_carrinho.widget(0))

        self.limpar_cliente()

        self.campo_desconto.setText("")
        self.campo_acrescimo.setText("")
        self.bloco_ajuste.setVisible(False)

        self.lbl_itens_valor.setText("0")
        self.lbl_itens_tabela.setText("0 itens")
        self.lbl_subtotal_valor.setText(formatar_moeda(0))
        self.lbl_desconto_valor.setText(formatar_moeda(0))
        self.lbl_acrescimo_valor.setText(formatar_moeda(0))
        self.lbl_desconto_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)
        self.lbl_acrescimo_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)

        self.total.setText("R$ 0,00")

        self.campo_codigo.setFocus()

    # ==================================================
    # VENDA SUSPENSA (pré-venda) — só em memória, some se o app
    # for fechado; sobrevive a navegar pra outra tela porque o
    # widget PDV nunca é recriado enquanto o app está aberto.
    # ==================================================

    def suspender_venda(self):

        if not self.itens:
            QMessageBox.warning(
                self, "Aviso", "Não há itens no carrinho pra suspender."
            )
            return

        rotulo = f"Venda {len(self.vendas_suspensas) + 1}"

        if self.cliente_nome:
            rotulo += f" — {self.cliente_nome}"

        self.vendas_suspensas.append({
            "rotulo": rotulo,
            "itens": [dict(item) for item in self.itens],
            "cliente_id": self.cliente_id,
            "cliente_nome": self.cliente_nome,
            "desconto_texto": self.campo_desconto.text(),
            "acrescimo_texto": self.campo_acrescimo.text(),
            "hora": datetime.now(),
        })

        self.limpar_venda()
        self._atualizar_botao_retomar()

        QMessageBox.information(
            self,
            "Venda suspensa",
            f'"{rotulo}" foi suspensa. Use "Vendas Suspensas" pra '
            "retomar de onde parou.",
        )

    def abrir_vendas_suspensas(self):

        dialogo = VendasSuspensasDialog(self.vendas_suspensas, parent=self)

        if dialogo.exec() != QDialog.Accepted or dialogo.indice_selecionado is None:
            return

        if dialogo.acao == "excluir":
            del self.vendas_suspensas[dialogo.indice_selecionado]
            self._atualizar_botao_retomar()
            return

        if self.itens:
            QMessageBox.warning(
                self,
                "Aviso",
                "Finalize, cancele ou suspenda a venda atual antes de "
                "retomar outra.",
            )
            return

        venda = self.vendas_suspensas.pop(dialogo.indice_selecionado)

        self.itens = venda["itens"]
        self.atualizar_tabela()

        if venda["cliente_id"]:
            self.definir_cliente({
                "id": venda["cliente_id"],
                "nome": venda["cliente_nome"],
            })
        else:
            self.limpar_cliente()

        self.campo_desconto.setText(venda["desconto_texto"])
        self.campo_acrescimo.setText(venda["acrescimo_texto"])
        self.bloco_ajuste.setVisible(
            bool(venda["desconto_texto"] or venda["acrescimo_texto"])
        )

        self._atualizar_botao_retomar()

    def _atualizar_botao_retomar(self):

        total = len(self.vendas_suspensas)

        self.bt_retomar.setText(
            f"Vendas Suspensas ({total})" if total else "Vendas Suspensas"
        )
        self.bt_retomar.setEnabled(total > 0)

    # ==================================================
    # ORÇAMENTO — imprime/exporta o carrinho atual sem finalizar a
    # venda. Não fica salvo nem listável em nenhum lugar: se virar
    # venda de verdade, é só continuar normalmente e ir em "Pagar".
    # ==================================================

    def imprimir_orcamento(self):

        if not self.itens:
            QMessageBox.warning(
                self, "Aviso", "Não há itens no carrinho pra gerar um orçamento."
            )
            return

        documento = self._montar_documento_orcamento()

        janela = QDialog(self)
        janela.setWindowTitle("Orçamento")
        janela.setFixedSize(360, 230)
        janela.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(janela)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        lbl = QLabel(
            "O orçamento não gera nenhuma venda — é só um documento "
            "pra levar ou enviar ao cliente."
        )
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(lbl)

        bt_imprimir = BotaoPrimario("Imprimir", icone_nome="printer")
        bt_imprimir.clicked.connect(
            lambda: self._imprimir_documento(documento, janela)
        )

        bt_pdf = BotaoSecundario("Salvar PDF")
        bt_pdf.clicked.connect(lambda: self._salvar_pdf_documento(documento))

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.clicked.connect(janela.accept)

        layout.addWidget(bt_imprimir)
        layout.addWidget(bt_pdf)
        layout.addWidget(bt_fechar)

        janela.exec()

    def _montar_documento_orcamento(self):

        config = configuracoes()
        nome_loja = config.get("nome_loja") or "Loja"

        subtotal = sum(item["preco"] * item["quantidade"] for item in self.itens)
        total = max(0.0, subtotal - self.desconto_valor + self.acrescimo_valor)

        linhas_itens = "".join(
            "<tr>"
            f"<td style='padding:4px 8px;'>{item['nome']}</td>"
            f"<td style='padding:4px 8px; text-align:center;'>{item['quantidade']}</td>"
            f"<td style='padding:4px 8px; text-align:right;'>{formatar_moeda(item['preco'])}</td>"
            f"<td style='padding:4px 8px; text-align:right;'>"
            f"{formatar_moeda(item['preco'] * item['quantidade'])}</td>"
            "</tr>"
            for item in self.itens
        )

        cliente_linha = (
            f"<p>Cliente: {self.cliente_nome}</p>" if self.cliente_nome else ""
        )

        html = f"""
        <html>
        <body style="font-family: Arial; font-size: 13px; color:#1E293B;">
            <h2 style="margin-bottom:0;">{nome_loja}</h2>
            <p style="color:#64748B; margin-top:2px;">
                Orçamento — {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </p>
            {cliente_linha}
            <table style="width:100%; border-collapse:collapse; margin-top:12px;">
                <tr style="background:#F1F5F9;">
                    <th style="padding:4px 8px; text-align:left;">Produto</th>
                    <th style="padding:4px 8px;">Qtd</th>
                    <th style="padding:4px 8px; text-align:right;">Unitário</th>
                    <th style="padding:4px 8px; text-align:right;">Subtotal</th>
                </tr>
                {linhas_itens}
            </table>
            <h3 style="text-align:right; margin-top:16px;">
                Total: {formatar_moeda(total)}
            </h3>
            <p style="color:#94A3B8; font-size:11px; margin-top:24px;">
                Este orçamento não tem valor fiscal e não gera nenhuma venda.
                Os valores podem mudar até a confirmação da compra.
            </p>
        </body>
        </html>
        """

        documento = QTextDocument()
        documento.setHtml(html)

        return documento

    def _imprimir_documento(self, documento, parent):

        printer = QPrinter(QPrinter.HighResolution)
        dialogo = QPrintDialog(printer, parent)

        if dialogo.exec() != QPrintDialog.Accepted:
            return

        documento.print_(printer)

    def _salvar_pdf_documento(self, documento):

        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar Orçamento", "orcamento.pdf", "Arquivo PDF (*.pdf)",
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".pdf"):
            caminho += ".pdf"

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(caminho)

        documento.print_(printer)

        QMessageBox.information(
            self, "Sucesso", "Orçamento salvo em PDF com sucesso."
        )

    # ==================================================
    # FINALIZAR VENDA (PAGAR - F3)
    # ==================================================

    def finalizar_venda(self):

        if not self.itens:
            QMessageBox.warning(
                self,
                "Aviso",
                "Nenhum produto foi adicionado."
            )

            return

        total = self._recalcular_totais()

        tela = PagamentoWindow(
            total,
            self.itens,
            cliente_id=self.cliente_id,
            cliente_nome=self.cliente_nome,
        )

        if tela.exec() != QDialog.Accepted:
            return

        desconto_liquido = self.desconto_valor - self.acrescimo_valor

        try:

            response = enviar_venda(
                itens=self.itens,
                forma_pagamento=tela.forma_pagamento,
                cliente_id=tela.cliente_id,
                desconto=desconto_liquido,
                observacao=tela.observacao.text().strip() or None,
                data_vencimento=None,
                forma_pagamento_2=tela.forma_pagamento_2,
                valor_forma_2=(
                    tela.valor_forma_2 if tela.forma_pagamento_2 else None
                ),
            )

            if response.status_code == 201:

                venda_criada = response.json()

                concluida = VendaConcluidaDialog(
                    venda_criada["id"],
                    total,
                    self.itens,
                    tela.forma_pagamento,
                    cliente_nome=tela.cliente_nome,
                    forma_pagamento_2=tela.forma_pagamento_2,
                    valor_forma_2=tela.valor_forma_2,
                    parent=self,
                )
                concluida.exec()

                self.limpar_venda()

            else:

                try:
                    erro = response.json()

                    if isinstance(erro, dict):
                        erro = erro.get(
                            "detail",
                            str(erro)
                        )

                except Exception:
                    erro = response.text

                QMessageBox.critical(
                    self,
                    "Erro",
                    f"Erro ao finalizar a venda.\n\n{erro}"
                )

        except Exception as e:

            QMessageBox.critical(
                self,
                "Erro",
                str(e)
            )
