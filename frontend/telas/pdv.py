from datetime import datetime, timedelta

from telas.pagamento import PagamentoWindow
from telas.buscar_produto import BuscarProdutoDialog
from telas.venda_concluida import VendaConcluidaDialog
from telas.cadastro_produto import CadastroProdutoWindow
from telas.selecionar_cliente import SelecionarClienteDialog
from services.venda_service import finalizar_venda as enviar_venda, listar_vendas
from services.produto_service import listar_produtos, cadastrar_produto
from services.pdv_service import buscar_produto
from services.caixa_service import caixa_aberto
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

        # Em telas mais baixas (notebooks, resoluções menores), a soma de
        # cabeçalho + código de barras + tabela + ajuste + resumo pode não
        # caber na janela — sem rolagem, o conteúdo de baixo (inclusive os
        # botões Buscar/Adicionar/Pagar) simplesmente ficava cortado fora
        # da área visível. A barra de atalhos fica FORA da área rolável,
        # de propósito: ela precisa estar sempre visível e alcançável,
        # nunca escondida atrás de uma rolagem.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        conteudo = QWidget()
        conteudo.setStyleSheet("background:transparent;")

        layout_conteudo = QVBoxLayout(conteudo)
        layout_conteudo.setContentsMargins(24, 20, 24, 0)
        layout_conteudo.setSpacing(14)

        layout_conteudo.addLayout(self._construir_cabecalho())
        layout_conteudo.addWidget(self._construir_campo_codigo())
        layout_conteudo.addWidget(self.lbl_status_busca)
        layout_conteudo.addWidget(self._construir_linha_cliente())
        layout_conteudo.addWidget(self._construir_mais_vendidos())
        layout_conteudo.addWidget(self._construir_tabela(), stretch=1)
        layout_conteudo.addWidget(self._construir_bloco_ajuste())
        layout_conteudo.addLayout(self._construir_resumo())

        self.tabela.setMinimumHeight(160)

        scroll.setWidget(conteudo)
        layout.addWidget(scroll, stretch=1)

        rodape = QVBoxLayout()
        rodape.setContentsMargins(24, 14, 24, 20)
        rodape.addLayout(self._construir_barra_atalhos())

        layout.addLayout(rodape)

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

        fade_in(self, duracao=200)

    def showEvent(self, event):
        super().showEvent(event)
        self.atualizar_indicador_caixa()
        self.atualizar_mais_vendidos()
        self.recarregar_atalhos()
        self.campo_codigo.setFocus()

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
        cabecalho.setSpacing(12)

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
        container.setFixedHeight(68)
        container.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border: 2px solid {tokens.PRIMARIA};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(14)

        lbl_icone = QLabel()
        lbl_icone.setStyleSheet("background:transparent;")
        lbl_icone.setPixmap(icone_pixmap("shopping-cart", cor=tokens.PRIMARIA, tamanho=26))
        layout.addWidget(lbl_icone)

        self.campo_codigo = QLineEdit()
        self.campo_codigo.setPlaceholderText(
            "Código de barras ou código do produto — pressione Enter"
        )
        self.campo_codigo.setFont(QFont(tokens.FONTE_FAMILIA_PADRAO, 20))
        self.campo_codigo.setStyleSheet(f"""
            QLineEdit {{
                border: none; background: transparent;
                color: {tokens.TEXTO}; font-size: 20px; font-weight: 600;
            }}
        """)
        self.campo_codigo.returnPressed.connect(self.processar_codigo)
        layout.addWidget(self.campo_codigo, stretch=1)

        dica = QLabel("F1 busca por nome")
        dica.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(dica)

        self.lbl_status_busca = QLabel("")
        self.lbl_status_busca.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; padding-left: 4px;
        """)

        return container

    def _construir_linha_cliente(self):

        linha = QFrame()
        linha.setStyleSheet("background:transparent; border:none;")

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        lbl_icone = QLabel()
        lbl_icone.setStyleSheet("background:transparent;")
        lbl_icone.setPixmap(icone_pixmap("users", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        layout.addWidget(lbl_icone)

        self.lbl_cliente = QLabel("Nenhum cliente selecionado")
        self.lbl_cliente.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(self.lbl_cliente)
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

        self.bt_selecionar_cliente = BotaoSecundario("Selecionar Cliente", icone_nome="users")
        self.bt_selecionar_cliente.setMinimumHeight(32)
        self.bt_selecionar_cliente.clicked.connect(self.abrir_selecionar_cliente)
        layout.addWidget(self.bt_selecionar_cliente)

        return linha

    def _construir_mais_vendidos(self):

        self.linha_mais_vendidos = QFrame()
        self.linha_mais_vendidos.setStyleSheet("background:transparent; border:none;")
        self.linha_mais_vendidos.setVisible(False)

        layout = QHBoxLayout(self.linha_mais_vendidos)
        layout.setContentsMargins(0, 0, 0, 0)
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
        últimos 30 dias — mesma agregação client-side já usada em
        relatorios.py (sem endpoint novo no backend)."""

        while self.layout_chips_mais_vendidos.count():
            item = self.layout_chips_mais_vendidos.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        try:
            vendas = listar_vendas()
            produtos = listar_produtos()
        except Exception:
            self.linha_mais_vendidos.setVisible(False)
            return

        produtos_por_id = {p["id"]: p for p in produtos}
        limite = datetime.now() - timedelta(days=30)

        qtd_por_produto = {}

        for venda in vendas:

            if venda.get("status") != "FINALIZADA":
                continue

            data_venda = _parse_data(venda.get("data"))

            if data_venda is None or data_venda < limite:
                continue

            for item in venda.get("itens", []):
                pid = item.get("produto_id")
                qtd_por_produto[pid] = qtd_por_produto.get(pid, 0) + item.get("quantidade", 0)

        top = sorted(qtd_por_produto.items(), key=lambda item: -item[1])[:5]
        exibidos = 0

        for pid, _qtd in top:

            produto = produtos_por_id.get(pid)

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

    def _construir_tabela(self):

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
        self.tabela.verticalHeader().setDefaultSectionSize(46)

        self.tabela.horizontalHeader().setStretchLastSection(False)
        self.tabela.setColumnWidth(2, 120)
        self.tabela.setColumnWidth(5, 48)
        self.tabela.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
                gridline-color: {tokens.BORDA};
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                font-size: {tokens.TAMANHO_BASE}px;
            }}
            QHeaderView::section {{
                background: {tokens.FUNDO};
                color: {tokens.TEXTO_SECUNDARIO};
                font-weight: 700;
                font-size: {tokens.TAMANHO_XS}px;
                padding: 8px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
            QTableWidget::item {{
                border-bottom: 1px solid {tokens.BORDA};
                padding: 4px;
            }}
        """)

        return self.tabela

    def _construir_bloco_ajuste(self):

        container = QWidget()
        container.setStyleSheet("background:transparent;")

        layout_container = QVBoxLayout(container)
        layout_container.setContentsMargins(0, 0, 0, 0)
        layout_container.setSpacing(8)

        self.bt_alternar_ajuste = QPushButton("+ Desconto ou acréscimo")
        self.bt_alternar_ajuste.setCursor(Qt.PointingHandCursor)
        self.bt_alternar_ajuste.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; text-align:left;
                color:{tokens.PRIMARIA}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:600; padding: 0;
            }}
        """)
        self.bt_alternar_ajuste.clicked.connect(self._alternar_bloco_ajuste)
        layout_container.addWidget(self.bt_alternar_ajuste)

        self.bloco_ajuste = QFrame()
        self.bloco_ajuste.setVisible(False)
        self.bloco_ajuste.setStyleSheet(f"""
            QFrame {{
                background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
            }}
        """)

        ajuste_layout = QHBoxLayout(self.bloco_ajuste)
        ajuste_layout.setContentsMargins(16, 14, 16, 14)
        ajuste_layout.setSpacing(16)

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
        ajuste_layout.addStretch()

        layout_container.addWidget(self.bloco_ajuste)

        return container

    def _construir_resumo(self):

        resumo = QHBoxLayout()

        col_itens = QVBoxLayout()
        col_itens.setSpacing(0)

        lbl_itens_titulo = QLabel("ITENS")
        lbl_itens_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        self.lbl_itens_valor = QLabel("0")
        self.lbl_itens_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XXL}px; font-weight:800;
        """)

        col_itens.addWidget(lbl_itens_titulo)
        col_itens.addWidget(self.lbl_itens_valor)

        col_total = QVBoxLayout()
        col_total.setSpacing(0)
        col_total.setAlignment(Qt.AlignRight)

        self.lbl_subtotal_info = QLabel("")
        self.lbl_subtotal_info.setAlignment(Qt.AlignRight)
        self.lbl_subtotal_info.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)
        self.lbl_subtotal_info.setVisible(False)

        self.total = QLabel("R$ 0,00")
        self.total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.total.setStyleSheet(f"""
            background:transparent; font-size: 38px; font-weight: 800;
            color: {tokens.SECUNDARIA};
        """)

        col_total.addWidget(self.lbl_subtotal_info)
        col_total.addWidget(self.total)

        resumo.addLayout(col_itens)
        resumo.addStretch()
        resumo.addLayout(col_total)

        return resumo

    def _construir_barra_atalhos(self):

        barra = QHBoxLayout()
        barra.setSpacing(14)

        self.bt_buscar = BotaoSecundario(
            f"Buscar ({self.atalhos['busca']})", icone_nome="search"
        )
        self.bt_buscar.setMinimumHeight(56)

        self.bt_adicionar = BotaoPrimario(
            f"Novo Produto ({self.atalhos['cadastro_rapido']})", icone_nome="plus"
        )
        self.bt_adicionar.setMinimumHeight(56)

        self.bt_pagar = BotaoSucesso("Pagar (F3)", icone_nome="credit-card")
        self.bt_pagar.setMinimumHeight(56)

        self.bt_buscar.clicked.connect(self.abrir_busca)
        self.bt_pagar.clicked.connect(self.finalizar_venda)
        self.bt_adicionar.clicked.connect(self.abrir_novo_produto)

        barra.addWidget(self.bt_buscar, stretch=1)
        barra.addWidget(self.bt_adicionar, stretch=1)
        barra.addWidget(self.bt_pagar, stretch=2)

        return barra

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
            font-size:{tokens.TAMANHO_SM}px;
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

            self.tabela.setItem(
                linha, 1, QTableWidgetItem(item["nome"])
            )

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

        self._recalcular_totais()
        self.campo_codigo.setFocus()

    def _recalcular_totais(self):

        subtotal = sum(item["preco"] * item["quantidade"] for item in self.itens)

        self.desconto_valor = _parse_valor(self.campo_desconto.text())
        self.acrescimo_valor = _parse_valor(self.campo_acrescimo.text())

        total = max(0.0, subtotal - self.desconto_valor + self.acrescimo_valor)

        self.lbl_itens_valor.setText(str(len(self.itens)))
        self.total.setText(formatar_moeda(total))

        if self.desconto_valor or self.acrescimo_valor:

            partes = [f"Subtotal {formatar_moeda(subtotal)}"]

            if self.desconto_valor:
                partes.append(f"desconto -{formatar_moeda(self.desconto_valor)}")

            if self.acrescimo_valor:
                partes.append(f"acréscimo +{formatar_moeda(self.acrescimo_valor)}")

            self.lbl_subtotal_info.setText("  ·  ".join(partes))
            self.lbl_subtotal_info.setVisible(True)

        else:
            self.lbl_subtotal_info.setVisible(False)

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

        self.limpar_cliente()

        self.campo_desconto.setText("")
        self.campo_acrescimo.setText("")
        self.bloco_ajuste.setVisible(False)

        self.lbl_itens_valor.setText("0")

        self.total.setText("R$ 0,00")
        self.lbl_subtotal_info.setVisible(False)

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
