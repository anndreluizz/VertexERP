from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem, QDialog

from telas.cadastro_produto import CadastroProdutoWindow
from telas.produto_criado import ProdutoCriadoDialog

from services.api import configuracoes
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
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QDialog,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import BotaoPerigo, BotaoPrimario, BotaoSecundario, CampoTexto, CardKPI
from widgets.banner import Banner


class Produtos(BaseCRUDWindow):

    titulo = "PRODUTOS"

    colunas = [
        "Código",
        "Nome",
        "Preço",
        "Estoque",
        "Status",
    ]

    campos = [
        "codigo",
        "nome",
        "preco_venda",
        "estoque",
        "ativo",
    ]

    voltar = Signal()

    def __init__(self):
        super().__init__()
        # BaseCRUDWindow já chama self.carregar() no final do próprio __init__,
        # então não é preciso chamar de novo aqui.

        self.produtos = []
        self.categorias = []
        self.filtro_categoria = None
        self.botoes_categoria = {}
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

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        config = configuracoes()
        nome_loja = config.get("nome_loja") or "Vertex ERP"

        titulo = QLabel(nome_loja)
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel("LOJA OPERACIONAL")
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
        # BANNERS DE AÇÃO
        # ======================

        banners_layout = QHBoxLayout()
        banners_layout.setSpacing(12)

        self.banner_novo = Banner(
            "PERSONALIZADO", "Novo Produto", "", tokens.SIDEBAR,
            icone_nome="plus",
        )

        self.banner_novo.clicado.connect(self.novo_produto)

        banners_layout.addWidget(self.banner_novo, stretch=1)

        conteudo_layout.addLayout(banners_layout)

        # ======================
        # BUSCA
        # ======================

        barra = QHBoxLayout()

        self.pesquisa = CampoTexto("Buscar produto pelo nome ou código de barras...")
        self.pesquisa.textChanged.connect(self.filtrar_produtos)

        barra.addWidget(self.pesquisa)

        conteudo_layout.addLayout(barra)

        # ======================
        # FILTRO DE CATEGORIAS
        # ======================

        self.categorias_layout = QHBoxLayout()
        self.categorias_layout.setSpacing(8)
        self.categorias_layout.addStretch()

        conteudo_layout.addLayout(self.categorias_layout)

        self.tabela = QTableWidget()

        self.tabela.setColumnCount(7)

        self.tabela.setHorizontalHeaderLabels([
            "Foto",
            "Código",
            "Produto",
            "Categoria",
            "Estoque",
            "Venda",
            "Status",
        ])

        self.tabela.verticalHeader().setDefaultSectionSize(60)

        self.tabela.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Fixed
        )
        self.tabela.setColumnWidth(0, 52)

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

        self.tabela.horizontalHeader().setStretchLastSection(True)

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
                background: {tokens.PRIMARIA};
                color: white;
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

        rodape = QHBoxLayout()

        self.bt_editar = BotaoPrimario("Editar", icone_nome="edit-2")
        self.bt_excluir = BotaoPerigo("Excluir", icone_nome="trash-2")
        self.bt_atualizar = BotaoSecundario("Atualizar", icone_nome="refresh-cw")

        rodape.addWidget(self.bt_editar)
        rodape.addWidget(self.bt_excluir)
        rodape.addStretch()
        rodape.addWidget(self.bt_atualizar)

        conteudo_layout.addLayout(rodape)

        # ==========================================
        # ATALHOS DE TECLADO E DUPLO CLIQUE
        # ==========================================
        QShortcut(QKeySequence("Delete"), self, self.excluir)
        QShortcut(QKeySequence("F5"), self, self.carregar)
        QShortcut(QKeySequence("Ctrl+N"), self, self.novo)

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

        self.bt_atualizar.clicked.connect(
            self.carregar
        )

        self.bt_editar.clicked.connect(
            self.editar_produto
        )

        self.bt_excluir.clicked.connect(
            self.excluir_produto
        )

        self.pesquisa.returnPressed.connect(
            self.filtrar_produtos
        )

        self.tabela.doubleClicked.connect(
            lambda index: self.editar_produto()
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
        self.card_patrimonio.definir_valor(f"R$ {patrimonio:.2f}")
        self.card_categorias.definir_valor(str(categorias_ativas))

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

        self.selecionar_categoria("TODOS")

    def selecionar_categoria(self, nome):

        self.filtro_categoria = None if nome == "TODOS" else nome

        for chave, botao in self.botoes_categoria.items():

            selecionado = chave == nome

            botao.setChecked(selecionado)

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.SIDEBAR if selecionado else tokens.CARD};
                    color: {"white" if selecionado else tokens.TEXTO};
                    border: 1px solid {tokens.SIDEBAR if selecionado else tokens.BORDA};
                    border-radius: {tokens.RADIUS_PILL}px;
                    padding: 0 14px;
                    font-weight: 700;
                    font-size: {tokens.TAMANHO_SM}px;
                }}
                QPushButton:hover {{
                    background: {"#33363b" if selecionado else tokens.FUNDO};
                }}
            """)

        self.filtrar_produtos()

    # ==========================================
    # FILTRAR PRODUTOS
    # ==========================================
    def filtrar(self):
        texto = self.pesquisa.text().lower().strip()

        produtos = self.produtos

        if self.filtro_categoria:

            produtos = [
                p
                for p in produtos
                if (p.get("categoria") or "") == self.filtro_categoria
            ]

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

        self.preencher_tabela(produtos)

    # ==========================================
    # PREENCHER TABELA
    # ==========================================
    def preencher_tabela(self, produtos):

        self.produtos_exibidos = produtos

        self.tabela.setRowCount(len(produtos))

        for linha, produto in enumerate(produtos):

            self.tabela.setCellWidget(
                linha,
                0,
                self._criar_widget_foto(produto)
            )

            codigo_exibido = (
                produto.get("codigo_barras")
                or produto["codigo"]
            )
            self.tabela.setItem(linha, 3, QTableWidgetItem(str(produto["estoque"])))

            self.tabela.setItem(
                linha,
                1,
                QTableWidgetItem(
                    str(codigo_exibido)
                )
            )

            self.tabela.setItem(
                linha,
                2,
                QTableWidgetItem(
                    produto["nome"]
                )
            )

            self.tabela.setItem(
                linha,
                3,
                QTableWidgetItem(
                    produto.get(
                        "categoria",
                        ""
                    ) or ""
                )
            )

            self.tabela.setItem(
                linha,
                4,
                QTableWidgetItem(
                    str(produto["estoque"])
                )
            )

            self.tabela.setItem(
                linha,
                5,
                QTableWidgetItem(
                    f'R$ {float(produto["preco_venda"]):.2f}'
                )
            )

            status = (
                "Ativo"
                if produto.get("ativo", True)
                else "Inativo"
            )

            self.tabela.setItem(
                linha,
                6,
                QTableWidgetItem(status)
            )

    # ==========================================
    # FOTO (MINIATURA COM CACHE)
    # ==========================================

    def _criar_widget_foto(self, produto):

        lbl = QLabel()
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setFixedSize(52, 52)

        pixmap = self._obter_pixmap_produto(produto)

        if pixmap:
            lbl.setPixmap(self._pixmap_circular(pixmap, 48))
        else:
            lbl.setStyleSheet(f"""
                background:{tokens.PRIMARIA_CLARA};
                border-radius:24px;
            """)
            lbl.setPixmap(icone_pixmap("package", cor=tokens.PRIMARIA, tamanho=20))

        return lbl

    def _pixmap_circular(self, pixmap, tamanho):

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

        circular = QPixmap(tamanho, tamanho)
        circular.fill(Qt.transparent)

        painter = QPainter(circular)
        painter.setRenderHint(QPainter.Antialiasing)

        caminho = QPainterPath()
        caminho.addEllipse(0, 0, tamanho, tamanho)
        painter.setClipPath(caminho)

        painter.drawPixmap(0, 0, origem)
        painter.end()

        return circular

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
    def novo(self):
        tela = CadastroProdutoWindow(codigo_sugerido=self._proximo_codigo())

        if tela.exec() != QDialog.Accepted:
            return

        response = cadastrar_produto(tela.dados)

        if response.status_code == 201:

            produto_criado = response.json()

            if tela.imagem_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(tela.imagem_bytes)
                self._cache_fotos[produto_criado["id"]] = pixmap

            sucesso = ProdutoCriadoDialog(
                produto_criado["nome"],
                float(produto_criado["preco_venda"]),
                tela.imagem_bytes,
                self,
            )
            sucesso.exec()

            self.carregar()

            if sucesso.editar_solicitado:
                self._abrir_edicao(produto_criado)

        else:
            self._exibir_erro(response)

    # ==========================================
    # EDITAR PRODUTO
    # ==========================================
    def editar(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um produto.")
            return

        produto = self.produtos_exibidos[linha]

        self._abrir_edicao(produto)

    def _abrir_edicao(self, produto):

        tela = CadastroProdutoWindow(produto)

        if tela.exec() != QDialog.Accepted:
            return

        response = atualizar_produto(produto["id"], tela.dados)

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
            self._exibir_erro(response)

    # ==========================================
    # EXCLUIR PRODUTO
    # ==========================================
    def excluir(self):
        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um produto.")
            return

        produto = self.produtos_exibidos[linha]

        resposta = QMessageBox.question(
            self,
            "Excluir Produto",
            f"Deseja excluir o produto\n\n{produto['nome']} ?",
        )

        if resposta != QMessageBox.Yes:
            return

        response = excluir_produto(produto["id"])

        if response.status_code == 200:
            QMessageBox.information(self, "Sucesso", "Produto excluído.")
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # PRÓXIMO CÓDIGO SEQUENCIAL
    # ==========================================
    def _proximo_codigo(self):
        maior = 0

            QMessageBox.critical(
                self,
                "Erro",
                erro,
            )
