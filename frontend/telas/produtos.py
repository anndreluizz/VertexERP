import csv

from PySide6.QtWidgets import QMessageBox

from telas.cadastro_produto import CadastroProdutoWindow
from telas.produto_criado import ProdutoCriadoDialog

from services.categoria_service import listar_categorias
from services.produto_service import (
    listar_produtos,
    cadastrar_produto,
    atualizar_produto,
    excluir_produto,
    obter_foto_produto,
)
from PySide6.QtCore import Qt, Signal

from PySide6.QtGui import (
    QShortcut,
    QKeySequence,
    QPixmap,
    QPainter,
    QPainterPath,
)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
    QFileDialog,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import Badge, BotaoPrimario, BotaoSecundario, CampoTexto, CardKPI
from utils.formatacao import formatar_moeda


# rótulo exibido -> chave interna do filtro de status
FILTROS_STATUS = [
    ("Todos", "TODOS"),
    ("Estoque baixo", "ESTOQUE_BAIXO"),
    ("Sem estoque", "SEM_ESTOQUE"),
    ("Ativos", "ATIVOS"),
    ("Inativos", "INATIVOS"),
]

_ICONES_FILTRO_STATUS = {
    "TODOS": "package",
    "ESTOQUE_BAIXO": "alert-triangle",
    "SEM_ESTOQUE": "x",
    "ATIVOS": "check",
    "INATIVOS": "eye-off",
}

# rótulo exibido -> chave interna da ordenação
ORDENACOES = [
    ("Mais recentes", "RECENTES"),
    ("Nome (A-Z)", "NOME_AZ"),
    ("Nome (Z-A)", "NOME_ZA"),
    ("Maior estoque", "ESTOQUE_DESC"),
    ("Menor estoque", "ESTOQUE_ASC"),
    ("Maior preço", "PRECO_DESC"),
    ("Menor preço", "PRECO_ASC"),
]


class Produtos(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.produtos = []
        self.produtos_exibidos = []
        self.categorias = []
        self.filtro_categoria = None
        self.filtro_status = "TODOS"
        self.ordenacao = "RECENTES"
        self.botoes_categoria = {}
        self.botoes_status = {}
        self._cache_fotos = {}

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
        icone_titulo.setPixmap(icone_pixmap("package", cor=tokens.PRIMARIA, tamanho=18))

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Produtos")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            "Gerencie seu estoque, cadastre novos produtos e mantenha "
            "tudo organizado."
        )
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        self.bt_importar = BotaoSecundario("Importar", icone_nome="arrow-down")
        self.bt_importar.clicked.connect(self.importar_nao_disponivel)

        self.bt_exportar = BotaoSecundario("Exportar", icone_nome="arrow-up")
        self.bt_exportar.clicked.connect(self.exportar_csv)

        self.bt_novo = BotaoPrimario("Novo Produto", icone_nome="plus")
        self.bt_novo.clicked.connect(self.novo_produto)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addWidget(icone_titulo)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(self.bt_importar)
        cabecalho.addWidget(self.bt_exportar)
        cabecalho.addWidget(self.bt_novo)

        layout.addLayout(cabecalho)

        # ======================
        # AREA ROLAVEL (todo o resto da pagina) -- so o cabecalho acima
        # fica fixo, o resto rola quando nao couber na tela.
        # ======================

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        conteudo = QWidget()
        conteudo.setStyleSheet("background:transparent;")

        conteudo_layout = QVBoxLayout(conteudo)
        conteudo_layout.setContentsMargins(0, 0, 0, 0)
        conteudo_layout.setSpacing(16)

        self.scroll.setWidget(conteudo)
        layout.addWidget(self.scroll, stretch=1)

        # ======================
        # CARDS DE RESUMO
        # ======================

        resumo_layout = QGridLayout()
        resumo_layout.setSpacing(14)

        self.card_total = CardKPI("Total de Produtos", "package", tokens.PRIMARIA)
        self.card_alerta = CardKPI("Estoque em Alerta", "alert-triangle", tokens.ALERTA)
        self.card_patrimonio = CardKPI("Valor em Estoque", "dollar-sign", tokens.SECUNDARIA)
        self.card_categorias = CardKPI("Categorias Ativas", "filter", tokens.PRIMARIA)

        resumo_layout.addWidget(self.card_total, 0, 0)
        resumo_layout.addWidget(self.card_alerta, 0, 1)
        resumo_layout.addWidget(self.card_patrimonio, 0, 2)
        resumo_layout.addWidget(self.card_categorias, 0, 3)

        for coluna in range(4):
            resumo_layout.setColumnStretch(coluna, 1)

        conteudo_layout.addLayout(resumo_layout)

        # ======================
        # BUSCA + FILTRO DE STATUS
        # ======================

        barra = QHBoxLayout()
        barra.setSpacing(10)

        self.pesquisa = CampoTexto("Buscar produto pelo nome ou código de barras...")
        self.pesquisa.textChanged.connect(self.filtrar_produtos)

        barra.addWidget(self.pesquisa, stretch=1)

        for rotulo, chave in FILTROS_STATUS:

            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setMinimumHeight(44)
            bt.setIcon(icone(
                _ICONES_FILTRO_STATUS.get(chave, "package"),
                cor=tokens.TEXTO_SECUNDARIO, tamanho=15,
            ))
            bt.clicked.connect(
                lambda checked, c=chave: self.selecionar_status(c)
            )

            self.botoes_status[chave] = bt
            barra.addWidget(bt)

        conteudo_layout.addLayout(barra)

        # ======================
        # FILTRO DE CATEGORIAS (ABAS) + ORDENAÇÃO
        # ======================

        linha_categorias = QHBoxLayout()
        linha_categorias.setSpacing(8)

        self.categorias_layout = QHBoxLayout()
        self.categorias_layout.setSpacing(8)

        linha_categorias.addLayout(self.categorias_layout, stretch=1)

        self.lbl_contagem = QLabel("")
        self.lbl_contagem.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        linha_categorias.addWidget(self.lbl_contagem)

        linha_categorias.addSpacing(8)

        self.combo_ordenacao = QComboBox()
        for rotulo, chave in ORDENACOES:
            self.combo_ordenacao.addItem(rotulo, chave)
        self.combo_ordenacao.setMinimumHeight(34)
        self.combo_ordenacao.currentIndexChanged.connect(self.alterar_ordenacao)

        linha_categorias.addWidget(self.combo_ordenacao)

        conteudo_layout.addLayout(linha_categorias)

        # ======================
        # TABELA
        # ======================

        self.tabela = QTableWidget()

        self.tabela.setColumnCount(9)

        self.tabela.setHorizontalHeaderLabels([
            "",
            "Foto",
            "Código",
            "Produto",
            "Categoria",
            "Estoque",
            "Preço de Venda",
            "Status",
            "Ações",
        ])

        self.tabela.verticalHeader().setDefaultSectionSize(64)

        self.tabela.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Fixed
        )
        self.tabela.setColumnWidth(0, 36)
        self.tabela.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Fixed
        )
        self.tabela.setColumnWidth(1, 60)
        self.tabela.horizontalHeader().setSectionResizeMode(
            8, QHeaderView.Fixed
        )
        self.tabela.setColumnWidth(8, 90)

        self.tabela.setAlternatingRowColors(True)

        self.tabela.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self.tabela.setSelectionMode(
            QTableWidget.SingleSelection
        )

        self.tabela.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        self.tabela.verticalHeader().setVisible(False)

        self.tabela.setShowGrid(False)

        self.tabela.itemChanged.connect(self._ao_mudar_checkbox)

        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                alternate-background-color: {tokens.FUNDO};
                font-size: {tokens.TAMANHO_BASE}px;
            }}
            QTableWidget::item:selected {{
                background: {tokens.PRIMARIA_CLARA};
                color: {tokens.TEXTO};
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
        """)

        self.tabela.setMinimumHeight(360)
        conteudo_layout.addWidget(self.tabela)

        # ======================
        # RODAPÉ
        # ======================

        rodape = QHBoxLayout()

        self.bt_excluir_selecionados = BotaoSecundario(
            "Excluir Selecionados", icone_nome="trash-2"
        )
        self.bt_excluir_selecionados.clicked.connect(self.excluir_selecionados)

        self.lbl_resumo_rodape = QLabel("")
        self.lbl_resumo_rodape.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        self.bt_atualizar = BotaoSecundario("Atualizar", icone_nome="refresh-cw")
        self.bt_atualizar.clicked.connect(self.carregar)

        rodape.addWidget(self.bt_excluir_selecionados)
        rodape.addStretch()
        rodape.addWidget(self.lbl_resumo_rodape)
        rodape.addSpacing(12)
        rodape.addWidget(self.bt_atualizar)

        conteudo_layout.addLayout(rodape)

        # ==========================================
        # DICAS DE ATALHOS
        # ==========================================

        dicas = QLabel(
            "Ctrl+N Novo produto    ·    "
            "F5 Atualizar    ·    "
            "Delete Excluir selecionado    ·    "
            "Duplo clique Editar"
        )

        dicas.setAlignment(Qt.AlignCenter)

        dicas.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; padding:6px;
        """)

        conteudo_layout.addWidget(dicas)

        conteudo_layout.addStretch()

        # ==========================================
        # EVENTOS
        # ==========================================

        self.pesquisa.returnPressed.connect(
            self.filtrar_produtos
        )

        self.tabela.doubleClicked.connect(
            lambda index: self.editar_produto()
            if index.column() not in (0, 8) else None
        )

        # ==========================================
        # ATALHOS DE TECLADO
        # ==========================================

        QShortcut(
            QKeySequence("Delete"),
            self,
            self.excluir_produto
        )

        QShortcut(
            QKeySequence("F5"),
            self,
            self.carregar
        )

        QShortcut(
            QKeySequence("Ctrl+N"),
            self,
            self.novo_produto
        )

        self._marcar_status_selecionado("TODOS")

        self.carregar()

    # ==========================================
    # CARREGAR PRODUTOS
    # ==========================================

    def carregar(self):

        self.produtos = listar_produtos()
        self.categorias = listar_categorias()

        self.atualizar_cards_resumo()
        self.atualizar_filtro_categorias()

        self.filtrar_produtos()

    # ==========================================
    # CARDS DE RESUMO
    # ==========================================

    def atualizar_cards_resumo(self):

        total = len(self.produtos)

        em_alerta = sum(
            1
            for p in self.produtos
            if p["estoque"] <= p.get("estoque_minimo", 0)
        )

        patrimonio = sum(
            float(p.get("preco_venda") or 0) * p["estoque"]
            for p in self.produtos
        )

        categorias_ativas = sum(
            1
            for c in self.categorias
            if c.get("ativo", True)
        )

        self.card_total.definir_valor(str(total))
        self.card_alerta.definir_valor(str(em_alerta))
        self.card_patrimonio.definir_valor(formatar_moeda(patrimonio))
        self.card_categorias.definir_valor(str(categorias_ativas))

        # sem selo de variação (ex.: "↑ 12%") aqui de propósito -- a
        # API não guarda um retrato de "produtos/valor em estoque de
        # ontem" pra comparar, então mostrar uma porcentagem seria
        # inventar um número (mesma decisão já tomada no Dashboard
        # pros cards sem base histórica confiável)

    # ==========================================
    # FILTRO DE STATUS
    # ==========================================

    def selecionar_status(self, chave):
        self._marcar_status_selecionado(chave)
        self.filtrar_produtos()

    def _marcar_status_selecionado(self, chave):

        self.filtro_status = chave

        for k, botao in self.botoes_status.items():

            selecionado = k == chave

            botao.setChecked(selecionado)
            botao.setIcon(icone(
                _ICONES_FILTRO_STATUS.get(k, "package"),
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

    # ==========================================
    # ORDENAÇÃO
    # ==========================================

    def alterar_ordenacao(self, _indice):
        self.ordenacao = self.combo_ordenacao.currentData()
        self.filtrar_produtos()

    def _ordenar(self, produtos):

        if self.ordenacao == "NOME_AZ":
            return sorted(produtos, key=lambda p: p["nome"].lower())
        if self.ordenacao == "NOME_ZA":
            return sorted(produtos, key=lambda p: p["nome"].lower(), reverse=True)
        if self.ordenacao == "ESTOQUE_DESC":
            return sorted(produtos, key=lambda p: p["estoque"], reverse=True)
        if self.ordenacao == "ESTOQUE_ASC":
            return sorted(produtos, key=lambda p: p["estoque"])
        if self.ordenacao == "PRECO_DESC":
            return sorted(produtos, key=lambda p: float(p.get("preco_venda") or 0), reverse=True)
        if self.ordenacao == "PRECO_ASC":
            return sorted(produtos, key=lambda p: float(p.get("preco_venda") or 0))

        # RECENTES -- sem "criado_em" na resposta da API, o id (auto-
        # incremento) é a melhor aproximação de "cadastrado por último"
        return sorted(produtos, key=lambda p: p["id"], reverse=True)

    # ==========================================
    # FILTRO DE CATEGORIAS (ABAS)
    # ==========================================

    def atualizar_filtro_categorias(self):

        while self.categorias_layout.count():
            item = self.categorias_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.botoes_categoria = {}

        nomes = ["TODOS"] + [
            c["nome"]
            for c in self.categorias
            if c.get("ativo", True)
        ]

        for nome in nomes:

            bt = QPushButton(nome)
            bt.setCheckable(True)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setMinimumHeight(32)
            bt.clicked.connect(
                lambda checked, n=nome: self.selecionar_categoria(n)
            )

            self.botoes_categoria[nome] = bt
            self.categorias_layout.addWidget(bt)

        self.categorias_layout.addStretch()

        self._marcar_categoria_selecionada("TODOS")

    def selecionar_categoria(self, nome):

        self.filtro_categoria = None if nome == "TODOS" else nome
        self._marcar_categoria_selecionada(nome)
        self.filtrar_produtos()

    def _marcar_categoria_selecionada(self, nome):

        for chave, botao in self.botoes_categoria.items():

            selecionado = chave == nome

            botao.setChecked(selecionado)

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.SIDEBAR if selecionado else tokens.CARD};
                    color: {tokens.TEXTO_CLARO if selecionado else tokens.TEXTO};
                    border: 1px solid {tokens.SIDEBAR if selecionado else tokens.BORDA};
                    border-radius: {tokens.RADIUS_PILL}px;
                    padding: 0 14px;
                    font-weight: 700;
                    font-size: {tokens.TAMANHO_SM}px;
                }}
                QPushButton:hover {{
                    background: {tokens.SIDEBAR_HOVER if selecionado else tokens.FUNDO};
                }}
            """)

    # ==========================================
    # FILTRAR PRODUTOS
    # ==========================================

    def filtrar_produtos(self):

        texto = self.pesquisa.text().lower().strip()

        produtos = self.produtos

        if self.filtro_categoria:

            produtos = [
                p
                for p in produtos
                if (p.get("categoria") or "") == self.filtro_categoria
            ]

        if self.filtro_status == "ESTOQUE_BAIXO":
            produtos = [
                p for p in produtos
                if 0 < p["estoque"] <= p.get("estoque_minimo", 0)
            ]
        elif self.filtro_status == "SEM_ESTOQUE":
            produtos = [p for p in produtos if p["estoque"] <= 0]
        elif self.filtro_status == "ATIVOS":
            produtos = [p for p in produtos if p.get("ativo", True)]
        elif self.filtro_status == "INATIVOS":
            produtos = [p for p in produtos if not p.get("ativo", True)]

        if texto != "":

            filtrados = []

            for produto in produtos:

                codigo = str(
                    produto["codigo"]
                ).lower()

                barras = str(
                    produto.get("codigo_barras") or ""
                ).lower()

                nome = str(
                    produto["nome"]
                ).lower()

                categoria = str(
                    produto.get("categoria") or ""
                ).lower()

                if (
                    texto in codigo
                    or texto in barras
                    or texto in nome
                    or texto in categoria
                ):

                    filtrados.append(produto)

            produtos = filtrados

        produtos = self._ordenar(produtos)

        self.preencher_tabela(produtos)

        total = len(produtos)
        self.lbl_contagem.setText(
            "1 produto encontrado" if total == 1
            else f"{total} produtos encontrados"
        )

        precisam_atencao = sum(
            1 for p in produtos if p["estoque"] <= p.get("estoque_minimo", 0)
        )
        self.lbl_resumo_rodape.setText(
            f"{total} produto(s)"
            + (f" · {precisam_atencao} precisam de atenção" if precisam_atencao else "")
        )

    # ==========================================
    # PREENCHER TABELA
    # ==========================================

    def preencher_tabela(self, produtos):

        self.produtos_exibidos = produtos

        self.tabela.blockSignals(True)

        # zera antes de repopular -- setCellWidget() por cima de uma
        # celula que ja tinha widget as vezes deixa o widget antigo
        # visualmente colado por baixo do novo (linhas fantasmas num
        # refresh); recriar as linhas do zero evita isso.
        self.tabela.setRowCount(0)
        self.tabela.setRowCount(len(produtos))

        for linha, produto in enumerate(produtos):

            item_check = QTableWidgetItem()
            item_check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item_check.setCheckState(Qt.Unchecked)
            self.tabela.setItem(linha, 0, item_check)

            self.tabela.setCellWidget(
                linha,
                1,
                self._criar_widget_foto(produto)
            )

            codigo_exibido = (
                produto.get("codigo_barras")
                or produto["codigo"]
            )

            self.tabela.setItem(
                linha,
                2,
                QTableWidgetItem(
                    str(codigo_exibido)
                )
            )

            self.tabela.setItem(
                linha,
                3,
                QTableWidgetItem(
                    produto["nome"]
                )
            )

            self.tabela.setCellWidget(
                linha, 4, self._badge_centralizado(
                    produto.get("categoria") or "—", "info"
                )
            )

            estoque = produto["estoque"]
            estoque_minimo = produto.get("estoque_minimo", 0)

            if estoque <= 0:
                variante_estoque = "erro"
            elif estoque <= estoque_minimo:
                variante_estoque = "alerta"
            else:
                variante_estoque = "sucesso"

            self.tabela.setCellWidget(
                linha, 5,
                self._badge_centralizado(str(estoque), variante_estoque)
            )

            self.tabela.setItem(
                linha,
                6,
                QTableWidgetItem(
                    formatar_moeda(produto["preco_venda"])
                )
            )

            ativo = produto.get("ativo", True)
            self.tabela.setCellWidget(
                linha, 7,
                self._badge_centralizado(
                    "Ativo" if ativo else "Inativo",
                    "sucesso" if ativo else "neutro",
                )
            )

            self.tabela.setCellWidget(
                linha, 8, self._widget_acoes(produto)
            )

        self.tabela.blockSignals(False)

        self._atualizar_texto_selecionados()

    def _badge_centralizado(self, texto, variante):

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)
        layout.addWidget(Badge(texto, variante))

        return container

    def _widget_acoes(self, produto):

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        bt_editar = QPushButton()
        bt_editar.setFixedSize(28, 28)
        bt_editar.setCursor(Qt.PointingHandCursor)
        bt_editar.setToolTip("Editar produto")
        bt_editar.setIcon(icone("edit-2", cor=tokens.PRIMARIA, tamanho=15))
        bt_editar.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{tokens.PRIMARIA_CLARA}; }}
        """)
        bt_editar.clicked.connect(lambda checked=False, p=produto: self._abrir_edicao(p))

        bt_excluir = QPushButton()
        bt_excluir.setFixedSize(28, 28)
        bt_excluir.setCursor(Qt.PointingHandCursor)
        bt_excluir.setToolTip("Excluir produto")
        bt_excluir.setIcon(icone("trash-2", cor=tokens.ERRO, tamanho=15))
        bt_excluir.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{tokens.ERRO_CLARO}; }}
        """)
        bt_excluir.clicked.connect(lambda checked=False, p=produto: self._excluir_um(p))

        layout.addWidget(bt_editar)
        layout.addWidget(bt_excluir)

        return container

    # ==========================================
    # SELEÇÃO EM MASSA
    # ==========================================

    def _ao_mudar_checkbox(self, item):
        if item.column() == 0:
            self._atualizar_texto_selecionados()

    def _produtos_selecionados(self):

        selecionados = []

        for linha, produto in enumerate(self.produtos_exibidos):
            item = self.tabela.item(linha, 0)
            if item and item.checkState() == Qt.Checked:
                selecionados.append(produto)

        return selecionados

    def _atualizar_texto_selecionados(self):

        quantidade = len(self._produtos_selecionados())

        if quantidade:
            self.bt_excluir_selecionados.setText(
                f"Excluir Selecionados ({quantidade})"
            )
        else:
            self.bt_excluir_selecionados.setText("Excluir Selecionados")

    def excluir_selecionados(self):

        selecionados = self._produtos_selecionados()

        if not selecionados:
            QMessageBox.warning(
                self, "Aviso", "Selecione ao menos um produto (marque a caixinha na primeira coluna)."
            )
            return

        nomes = ", ".join(p["nome"] for p in selecionados[:3])
        if len(selecionados) > 3:
            nomes += f" e mais {len(selecionados) - 3}"

        resposta = QMessageBox.question(
            self,
            "Excluir Produtos",
            f"Deseja excluir {len(selecionados)} produto(s)?\n\n{nomes}",
        )

        if resposta != QMessageBox.Yes:
            return

        falhas = []

        for produto in selecionados:
            response = excluir_produto(produto["id"])
            if response.status_code != 200:
                falhas.append(produto["nome"])

        self.carregar()

        if falhas:
            QMessageBox.critical(
                self,
                "Erro",
                "Não foi possível excluir: " + ", ".join(falhas),
            )
        else:
            QMessageBox.information(
                self, "Sucesso", f"{len(selecionados)} produto(s) excluído(s)."
            )

    # ==========================================
    # FOTO (MINIATURA COM CACHE)
    # ==========================================

    def _criar_widget_foto(self, produto):

        lbl = QLabel()
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFixedSize(48, 48)

        pixmap = self._obter_pixmap_produto(produto)

        if pixmap:
            lbl.setPixmap(self._pixmap_arredondado(pixmap, 44, raio=10))
        else:
            lbl.setStyleSheet(f"""
                background:{tokens.PRIMARIA_CLARA};
                border-radius:{tokens.RADIUS_SM}px;
            """)
            lbl.setPixmap(icone_pixmap("package", cor=tokens.PRIMARIA, tamanho=18))

        return lbl

    def _pixmap_arredondado(self, pixmap, tamanho, raio=10):

        origem = pixmap.scaled(
            tamanho,
            tamanho,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )

        if origem.width() != tamanho or origem.height() != tamanho:
            x = (origem.width() - tamanho) // 2
            y = (origem.height() - tamanho) // 2
            origem = origem.copy(x, y, tamanho, tamanho)

        arredondado = QPixmap(tamanho, tamanho)
        arredondado.fill(Qt.transparent)

        painter = QPainter(arredondado)
        painter.setRenderHint(QPainter.Antialiasing)

        caminho = QPainterPath()
        caminho.addRoundedRect(0, 0, tamanho, tamanho, raio, raio)
        painter.setClipPath(caminho)

        painter.drawPixmap(0, 0, origem)
        painter.end()

        return arredondado

    def _obter_pixmap_produto(self, produto):

        produto_id = produto["id"]

        if produto_id in self._cache_fotos:
            return self._cache_fotos[produto_id]

        pixmap = None

        if produto.get("tem_foto"):

            foto_bytes = obter_foto_produto(produto_id)

            if foto_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(foto_bytes)

        self._cache_fotos[produto_id] = pixmap

        return pixmap

    # ==========================================
    # NOVO PRODUTO
    # ==========================================

    def novo_produto(self):

        tela = CadastroProdutoWindow()

        if tela.exec() != QDialog.Accepted:
            return

        response = cadastrar_produto(
            tela.dados
        )

        if response.status_code == 201:

            produto_criado = response.json()

            if tela.imagem_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(tela.imagem_bytes)
                self._cache_fotos[produto_criado["id"]] = pixmap

            sucesso = ProdutoCriadoDialog(
                produto_criado,
                tela.imagem_bytes,
                self,
            )
            sucesso.exec()

            self.carregar()

            if sucesso.editar_solicitado:
                self._abrir_edicao(produto_criado)
            elif sucesso.cadastrar_outro_solicitado:
                self.novo_produto()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(
                self,
                "Erro",
                erro,
            )

    # ==========================================
    # EDITAR PRODUTO
    # ==========================================

    def editar_produto(self):

        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(
                self,
                "Aviso",
                "Selecione um produto."
            )
            return

        produto = self.produtos_exibidos[linha]

        self._abrir_edicao(produto)

    def _abrir_edicao(self, produto):

        tela = CadastroProdutoWindow(produto)

        if tela.exec() != QDialog.Accepted:
            return

        response = atualizar_produto(
            produto["id"],
            tela.dados,
        )

        if response.status_code == 200:

            if tela.imagem_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(tela.imagem_bytes)
                self._cache_fotos[produto["id"]] = pixmap

            QMessageBox.information(
                self,
                "Sucesso",
                "Produto atualizado com sucesso."
            )

            self.carregar()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(
                self,
                "Erro",
                erro,
            )

    # ==========================================
    # EXCLUIR PRODUTO
    # ==========================================

    def excluir_produto(self):

        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(
                self,
                "Aviso",
                "Selecione um produto."
            )
            return

        self._excluir_um(self.produtos_exibidos[linha])

    def _excluir_um(self, produto):

        resposta = QMessageBox.question(
            self,
            "Excluir Produto",
            f"Deseja excluir o produto\n\n{produto['nome']} ?"
        )

        if resposta != QMessageBox.Yes:
            return

        response = excluir_produto(
            produto["id"]
        )

        if response.status_code == 200:

            QMessageBox.information(
                self,
                "Sucesso",
                "Produto excluído."
            )

            self.carregar()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(
                self,
                "Erro",
                erro,
            )

    # ==========================================
    # IMPORTAR / EXPORTAR
    # ==========================================

    def importar_nao_disponivel(self):

        QMessageBox.information(
            self,
            "Importar Produtos",
            "A importação em massa por CSV ainda não foi implementada "
            "-- por enquanto, cadastre os produtos um a um em "
            "\"Novo Produto\".",
        )

    def exportar_csv(self):

        if not self.produtos_exibidos:
            QMessageBox.information(
                self,
                "Nada para exportar",
                "Não há produtos na lista atual pra exportar.",
            )
            return

        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Produtos (CSV)",
            "produtos.csv",
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
                    "Código", "Código de Barras", "Produto", "Categoria",
                    "Estoque", "Estoque Mínimo", "Preço de Venda", "Status",
                ])

                for produto in self.produtos_exibidos:
                    escritor.writerow([
                        produto["codigo"],
                        produto.get("codigo_barras") or "",
                        produto["nome"],
                        produto.get("categoria") or "",
                        produto["estoque"],
                        produto.get("estoque_minimo", 0),
                        formatar_moeda(produto["preco_venda"]),
                        "Ativo" if produto.get("ativo", True) else "Inativo",
                    ])

            QMessageBox.information(
                self, "Sucesso", "Produtos exportados com sucesso."
            )

        except OSError as erro:
            QMessageBox.critical(self, "Erro", str(erro))
