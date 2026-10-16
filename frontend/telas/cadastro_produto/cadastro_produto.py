from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt, QTimer, QDate
from PySide6.QtGui import QKeySequence, QShortcut

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QLabel,
    QPlainTextEdit,
    QComboBox,
    QSpinBox,
    QPushButton,
    QCheckBox,
    QGridLayout,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
)

import base64

from telas.historico_precos import HistoricoPrecosDialog
from services.produto_service import (
    obter_foto_produto,
)
from services.worker import rodar_em_thread
from widgets.tables.standard_table import StandardTable
from design import tokens
from design.icons import icone, icone_pixmap
from design.responsive import tamanho_fixo_seguro
from design.widgets import (
    Badge, BotaoSecundario, BotaoSucesso, CabecalhoDialogo,
)
from utils.formatacao import formatar_moeda
from utils.maiusculas import forcar_maiusculas
from telas.cadastro_produto.busca_externa import BuscaExternaMixin
from telas.cadastro_produto.categorias_marcas import CategoriasMarcasMixin
from telas.cadastro_produto.comum import _FOTO_ALTURA, _FOTO_LARGURA, _LARGURA_COLUNA_DIREITA
from telas.cadastro_produto.formulario import FormularioMixin
from telas.cadastro_produto.fotos import FotosMixin
from telas.cadastro_produto.kit_variacoes import KitVariacoesMixin


class CadastroProdutoWindow(FormularioMixin, CategoriasMarcasMixin, KitVariacoesMixin, BuscaExternaMixin, FotosMixin, QDialog):
    """Cadastro de produto em duas colunas: à esquerda os dados
    (Identificação, Preço e estoque, Promoção e -- editando -- Kit e
    Variações), à direita a foto e um resumo ao vivo de preço, custo,
    lucro, margem e estoque. Tudo visível de uma vez (sem o antigo
    "Mais opções" recolhido); Enter continua andando pelos campos
    essenciais e cadastra no último."""

    def __init__(self, produto=None, produto_pai=None):
        super().__init__()

        self.produto = produto
        self.produto_pai = produto_pai
        self.produto_pai_id = (
            produto_pai["id"] if produto_pai
            else (produto.get("produto_pai_id") if produto else None)
        )
        # variacao de variacao nao e' permitido -- so' produto "raiz"
        # (sem pai) pode ganhar o painel de gerenciar variacoes
        self._pode_ter_variacoes = self.produto_pai_id is None
        self.imagem_bytes = None
        self.modo_venda = "UN"

        if produto:
            titulo_texto = "Editar Produto"
            subtitulo_texto = "Atualize os dados do produto no sistema."
        elif produto_pai:
            titulo_texto = f"Nova Variação de \"{produto_pai['nome']}\""
            subtitulo_texto = "Mesmo produto em outra cor/tamanho, com código e estoque próprios."
        else:
            titulo_texto = "Novo Produto"
            subtitulo_texto = "Bipe o código de barras ou digite o nome. Enter passa pro próximo campo."

        self.setWindowTitle(titulo_texto)
        self.setStyleSheet(f"background:{tokens.FUNDO};")
        tamanho_fixo_seguro(self, 1200, 880)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = CabecalhoDialogo(
            "package", tokens.PRIMARIA, tokens.PRIMARIA_CLARA,
            titulo_texto, subtitulo_texto,
            fechavel=True, ao_fechar=self.reject,
        )
        cabecalho.setStyleSheet(f"background:{tokens.CARD};")

        self.favorito = QPushButton("Favorito")
        self.favorito.setCheckable(True)
        self.favorito.setCursor(Qt.PointingHandCursor)
        self.favorito.setMinimumHeight(36)
        self.favorito.setToolTip("Produtos favoritos ficam em destaque na busca do PDV")
        self.favorito.toggled.connect(self._atualizar_estilo_favorito)
        # entra antes do X: a linha do CabecalhoDialogo é
        # [ícone, títulos, stretch, X]
        cabecalho.layout().itemAt(0).layout().insertWidget(3, self.favorito)

        layout.addWidget(cabecalho)

        # ======================
        # CORPO (rola só na vertical)
        # ======================

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        corpo_widget = QWidget()
        corpo_widget.setStyleSheet("background:transparent;")

        corpo = QHBoxLayout(corpo_widget)
        corpo.setContentsMargins(28, 20, 28, 20)
        corpo.setSpacing(20)

        esquerda = QVBoxLayout()
        esquerda.setSpacing(16)
        direita = QVBoxLayout()
        direita.setSpacing(16)

        # ---------- Identificação ----------

        cartao_ident, corpo_ident = self._construir_cartao_secao(
            "Identificação", "Como o produto aparece na busca, no PDV e no cupom.",
            "edit-2", tokens.PRIMARIA,
        )

        self.codigo_barras = self._input("Bipar ou digitar o código de barras...")
        # Enter (o leitor de codigo manda um no fim) busca em silencio
        # -- bolsa/roupa quase nunca esta' na base publica e um aviso
        # "nao encontrado" a cada bipada travaria o cadastro rapido.
        # O botao de lupa continua avisando.
        self.codigo_barras.returnPressed.connect(
            lambda: self.buscar_automatico(silencioso=True)
        )
        self.codigo_barras.textChanged.connect(self.agendar_busca_automatica)

        self.timer_busca_automatica = QTimer(self)
        self.timer_busca_automatica.setSingleShot(True)
        self.timer_busca_automatica.timeout.connect(
            lambda: self.buscar_automatico(silencioso=True)
        )

        self.bt_buscar = QPushButton()
        self.bt_buscar.setCursor(Qt.PointingHandCursor)
        self.bt_buscar.setFixedSize(44, 44)
        self.bt_buscar.setToolTip("Consultar produto pelo código (Open Food Facts)")
        self.bt_buscar.setAccessibleName("Consultar produto pelo código")
        self.bt_buscar.setIcon(icone("search", cor="white", tamanho=18))
        self.bt_buscar.setStyleSheet(f"""
            QPushButton {{ background:{tokens.PRIMARIA}; border-radius:{tokens.RADIUS_SM}px; }}
            QPushButton:hover {{ background:{tokens.PRIMARIA_HOVER}; }}
        """)
        self.bt_buscar.clicked.connect(lambda: self.buscar_automatico(silencioso=False))

        self.nome = self._input("Ex.: Mochila Preta Escolar")

        self.categoria = QComboBox()
        self.categoria.setEditable(True)
        self.categoria.setMinimumHeight(44)
        self.categoria.setStyleSheet(self._estilo_input("QComboBox"))
        self._carregar_categorias()

        self.bt_nova_categoria = self._botao_icone("plus", "Criar nova categoria", self.criar_nova_categoria)
        self.bt_gerenciar_categorias = self._botao_icone(
            "menu", "Gerenciar categorias (editar/excluir)", self.gerenciar_categorias,
        )

        self.marca = QComboBox()
        self.marca.setEditable(False)
        self.marca.setMinimumHeight(44)
        self.marca.setStyleSheet(self._estilo_input("QComboBox"))
        self._carregar_marcas()

        self.bt_nova_marca = self._botao_icone("plus", "Criar nova marca", self.criar_nova_marca)
        self.bt_gerenciar_marcas = self._botao_icone(
            "menu", "Gerenciar marcas (editar/excluir)", self.gerenciar_marcas,
        )

        self.colecao = self._input("Ex.: Verão 2026, Linha Premium...")
        self.cor = self._input("Ex.: Azul")
        self.tamanho = self._input("Ex.: P, M, 42...")

        self.descricao = QPlainTextEdit()
        self.descricao.setPlaceholderText("Ex.: refrigerante, embalagem, sabor, observações...")
        self.descricao.setFixedHeight(80)
        self.descricao.setStyleSheet(f"""
            QPlainTextEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 8px 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QPlainTextEdit:focus {{ border-color: {tokens.PRIMARIA}; }}
        """)
        self.descricao.textChanged.connect(self._limitar_descricao)

        self.lbl_contador_descricao = QLabel("0/300")
        self.lbl_contador_descricao.setAlignment(Qt.AlignRight)
        self.lbl_contador_descricao.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        grade_ident = QGridLayout()
        grade_ident.setHorizontalSpacing(14)
        grade_ident.setVerticalSpacing(14)
        grade_ident.addWidget(self._campo(
            "Código de barras", self._linha(self.codigo_barras, self.bt_buscar),
        ), 0, 0, 1, 3)
        grade_ident.addWidget(self._campo("Nome do produto", self.nome, obrigatorio=True), 1, 0, 1, 3)
        grade_ident.addWidget(self._campo(
            "Categoria", self._linha(self.categoria, self.bt_nova_categoria, self.bt_gerenciar_categorias),
        ), 2, 0, 1, 2)
        grade_ident.addWidget(self._campo(
            "Marca", self._linha(self.marca, self.bt_nova_marca, self.bt_gerenciar_marcas),
        ), 2, 2)
        grade_ident.addWidget(self._campo("Coleção", self.colecao), 3, 0)
        grade_ident.addWidget(self._campo("Cor", self.cor), 3, 1)
        grade_ident.addWidget(self._campo("Tamanho", self.tamanho), 3, 2)
        grade_ident.addWidget(self._campo("Descrição", self.descricao), 4, 0, 1, 3)
        grade_ident.addWidget(self.lbl_contador_descricao, 5, 0, 1, 3)
        for coluna in range(3):
            grade_ident.setColumnStretch(coluna, 1)
        corpo_ident.addLayout(grade_ident)

        esquerda.addWidget(cartao_ident)

        # ---------- Preço e estoque ----------

        cartao_preco, corpo_preco = self._construir_cartao_secao(
            "Preço e estoque", "O custo é opcional, mas é ele que mostra o lucro.",
            "dollar-sign", tokens.SECUNDARIA,
        )

        self.preco_venda = self._dinheiro()
        self.preco_custo = self._dinheiro()

        self.estoque = QSpinBox()
        self.estoque.setMaximum(999999)
        self.estoque.setMinimumHeight(44)
        self.estoque.setStyleSheet(self._estilo_input("QSpinBox"))

        self.estoque_minimo = QSpinBox()
        self.estoque_minimo.setMaximum(999999)
        self.estoque_minimo.setMinimumHeight(44)
        self.estoque_minimo.setToolTip(
            "Quando o estoque atingir o mínimo, o produto aparece no alerta de estoque."
        )
        self.estoque_minimo.setStyleSheet(self._estilo_input("QSpinBox"))

        # UN/KG/L -- define a unidade do produto
        seletor_modo = QWidget()
        seletor_modo.setStyleSheet("background:transparent;")
        linha_modo = QHBoxLayout(seletor_modo)
        linha_modo.setContentsMargins(0, 0, 0, 0)
        linha_modo.setSpacing(4)
        self.botoes_modo = {}
        for rotulo, valor in [("Unidade", "UN"), ("Kg", "KG"), ("Litro", "L")]:
            bt = QPushButton(rotulo)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setCheckable(True)
            bt.setMinimumHeight(44)
            bt.clicked.connect(lambda checked, v=valor: self.selecionar_modo(v))
            self.botoes_modo[valor] = bt
            linha_modo.addWidget(bt)

        self.lbl_margem = QLabel()
        self.lbl_margem.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        grade_preco = QGridLayout()
        grade_preco.setHorizontalSpacing(14)
        grade_preco.setVerticalSpacing(14)
        grade_preco.addWidget(self._campo("Preço de venda (R$)", self.preco_venda, obrigatorio=True), 0, 0)
        grade_preco.addWidget(self._campo("Custo de compra (R$)", self.preco_custo), 0, 1)
        grade_preco.addWidget(self._campo("Vendido por", seletor_modo), 0, 2)
        grade_preco.addWidget(self.lbl_margem, 1, 0, 1, 3)
        grade_preco.addWidget(self._campo(
            "Estoque atual" if produto else "Estoque inicial", self.estoque,
        ), 2, 0)
        grade_preco.addWidget(self._campo("Estoque mínimo (alerta)", self.estoque_minimo), 2, 1)
        for coluna in range(3):
            grade_preco.setColumnStretch(coluna, 1)
        corpo_preco.addLayout(grade_preco)

        esquerda.addWidget(cartao_preco)

        # ---------- Promoção ----------

        cartao_promo, corpo_promo = self._construir_cartao_secao(
            "Promoção", "Preço especial por um período -- volta sozinho ao normal depois.",
            "trending-up", tokens.ALERTA,
        )

        linha_promocao_titulo = QHBoxLayout()
        self.em_promocao_check = QCheckBox("Ativar preço promocional")
        self.em_promocao_check.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO}; "
            f"font-weight:600; font-size:{tokens.TAMANHO_SM}px;"
        )
        self.em_promocao_check.toggled.connect(self._alternar_promocao)

        self.bt_historico_precos = QPushButton("Histórico de preços")
        self.bt_historico_precos.setCursor(Qt.PointingHandCursor)
        self.bt_historico_precos.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{tokens.PRIMARIA};
                font-weight:700; font-size:{tokens.TAMANHO_SM}px; border:none; padding:0;
            }}
            QPushButton:hover {{ color:{tokens.PRIMARIA_HOVER}; }}
        """)
        self.bt_historico_precos.clicked.connect(self.ver_historico_precos)
        self.bt_historico_precos.setVisible(self.produto is not None)

        linha_promocao_titulo.addWidget(self.em_promocao_check)
        linha_promocao_titulo.addStretch()
        linha_promocao_titulo.addWidget(self.bt_historico_precos)
        corpo_promo.addLayout(linha_promocao_titulo)

        self.preco_promocional = self._dinheiro()
        self.promocao_inicio = self._data(QDate.currentDate())
        self.promocao_fim = self._data(QDate.currentDate().addDays(7))

        grade_promo = QGridLayout()
        grade_promo.setHorizontalSpacing(14)
        grade_promo.addWidget(self._campo("Preço promocional (R$)", self.preco_promocional), 0, 0)
        grade_promo.addWidget(self._campo("Válida de", self.promocao_inicio), 0, 1)
        grade_promo.addWidget(self._campo("Até", self.promocao_fim), 0, 2)
        for coluna in range(3):
            grade_promo.setColumnStretch(coluna, 1)
        corpo_promo.addLayout(grade_promo)

        self._alternar_promocao(False)
        esquerda.addWidget(cartao_promo)

        # ---------- Kit / Combo ----------

        cartao_kit, corpo_kit = self._construir_cartao_secao(
            "Kit / Combo",
            "Venda vários produtos como um só -- o estoque baixado é o dos "
            "componentes, não o do kit.",
            "package", tokens.ALERTA,
        )

        self.eh_kit_check = QCheckBox("Este produto é um kit/combo")
        self.eh_kit_check.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO}; "
            f"font-weight:600; font-size:{tokens.TAMANHO_SM}px;"
        )
        self.eh_kit_check.toggled.connect(self._alternar_kit)
        corpo_kit.addWidget(self.eh_kit_check)

        self.painel_kit = QWidget()
        layout_painel_kit = QVBoxLayout(self.painel_kit)
        layout_painel_kit.setContentsMargins(0, 0, 0, 0)
        layout_painel_kit.setSpacing(8)

        self.tabela_kit = StandardTable(["Componente", "Quantidade"])
        self.tabela_kit.setMaximumHeight(160)
        layout_painel_kit.addWidget(self.tabela_kit)

        linha_botoes_kit = QHBoxLayout()
        linha_botoes_kit.setSpacing(8)
        self.bt_adicionar_componente = BotaoSecundario("Adicionar componente", icone_nome="plus")
        self.bt_adicionar_componente.clicked.connect(self.adicionar_componente_kit)
        self.bt_remover_componente = BotaoSecundario("Remover selecionado", icone_nome="trash-2")
        self.bt_remover_componente.clicked.connect(self.remover_componente_kit)
        linha_botoes_kit.addWidget(self.bt_adicionar_componente)
        linha_botoes_kit.addWidget(self.bt_remover_componente)
        linha_botoes_kit.addStretch()
        layout_painel_kit.addLayout(linha_botoes_kit)

        corpo_kit.addWidget(self.painel_kit)

        if self.produto is None:
            self.painel_kit.setVisible(False)
        else:
            self.kit_itens = []
            self._carregar_itens_kit()

        self._alternar_kit(False)

        # kit e variação precisam do id do produto -- só aparecem
        # editando; a referência segura os cartões vivos porque os
        # métodos ainda leem eh_kit_check/painel_kit
        self._cartao_kit = cartao_kit
        if self.produto:
            esquerda.addWidget(cartao_kit)

        # ---------- Variações ----------

        if self._pode_ter_variacoes:

            cartao_variacoes, corpo_variacoes = self._construir_cartao_secao(
                "Variações",
                "Mesmo produto em cores/tamanhos diferentes, cada um com "
                "código e estoque próprios.",
                "package", tokens.SECUNDARIA,
            )

            self.tabela_variacoes = StandardTable(["Nome", "Cor", "Tamanho", "Estoque"])
            self.tabela_variacoes.setMaximumHeight(160)
            corpo_variacoes.addWidget(self.tabela_variacoes)

            self.bt_nova_variacao = BotaoSecundario("Nova variação", icone_nome="plus")
            self.bt_nova_variacao.clicked.connect(self.nova_variacao)
            linha_variacao = QHBoxLayout()
            linha_variacao.addWidget(self.bt_nova_variacao)
            linha_variacao.addStretch()
            corpo_variacoes.addLayout(linha_variacao)

            if self.produto is None:
                self.bt_nova_variacao.setEnabled(False)
            else:
                self._carregar_variacoes()

            self._cartao_variacoes = cartao_variacoes
            if self.produto:
                esquerda.addWidget(cartao_variacoes)

        esquerda.addStretch()

        # ---------- Foto (coluna direita) ----------

        cartao_foto, corpo_foto = self._construir_cartao_secao(
            "Foto", "Aparece na busca e no PDV.", "eye", tokens.PRIMARIA,
        )

        self.lbl_foto = QLabel()
        self.lbl_foto.setFixedSize(_FOTO_LARGURA, _FOTO_ALTURA)
        self.lbl_foto.setAlignment(Qt.AlignCenter)
        self.lbl_foto.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_MD}px;
        """)
        self.lbl_foto.setPixmap(icone_pixmap("package", cor=tokens.TEXTO_TERCIARIO, tamanho=44))
        corpo_foto.addWidget(self.lbl_foto, 0, Qt.AlignHCenter)

        self.bt_adicionar_imagem = QPushButton("Escolher imagem  ·  PNG, JPG ou WEBP")
        self.bt_adicionar_imagem.setCursor(Qt.PointingHandCursor)
        self.bt_adicionar_imagem.setMinimumHeight(40)
        self.bt_adicionar_imagem.setIcon(icone("plus", cor=tokens.PRIMARIA, tamanho=15))
        self.bt_adicionar_imagem.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; border:1.5px dashed {tokens.BORDA_FORTE};
                border-radius:{tokens.RADIUS_SM}px; color:{tokens.PRIMARIA};
                font-weight:600; font-size:{tokens.TAMANHO_SM}px; padding:0 12px;
            }}
            QPushButton:hover {{ background:{tokens.PRIMARIA_CLARA}; border-color:{tokens.PRIMARIA}; }}
        """)
        self.bt_adicionar_imagem.clicked.connect(self.adicionar_imagem)
        corpo_foto.addWidget(self.bt_adicionar_imagem)

        # galeria de fotos adicionais -- só editando: anexar foto extra
        # usa POST /produtos/{id}/fotos, que precisa do id do produto
        if self.produto:

            lbl_galeria = QLabel("Mais fotos (a estrela torna principal)")
            lbl_galeria.setWordWrap(True)
            lbl_galeria.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_SECUNDARIO};
                font-size:{tokens.TAMANHO_XS}px; font-weight:600; margin-top:4px;
            """)
            corpo_foto.addWidget(lbl_galeria)

            self.linha_galeria = QHBoxLayout()
            self.linha_galeria.setSpacing(8)

            self.bt_adicionar_foto_extra = QPushButton()
            self.bt_adicionar_foto_extra.setFixedSize(56, 56)
            self.bt_adicionar_foto_extra.setCursor(Qt.PointingHandCursor)
            self.bt_adicionar_foto_extra.setToolTip("Adicionar mais uma foto")
            self.bt_adicionar_foto_extra.setAccessibleName("Adicionar mais uma foto")
            self.bt_adicionar_foto_extra.setIcon(icone("plus", cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
            self.bt_adicionar_foto_extra.setStyleSheet(f"""
                QPushButton {{
                    background:{tokens.FUNDO}; border:1.5px dashed {tokens.BORDA_FORTE};
                    border-radius:{tokens.RADIUS_SM}px;
                }}
                QPushButton:hover {{ background:{tokens.BORDA}; }}
            """)
            self.bt_adicionar_foto_extra.clicked.connect(self.adicionar_foto_extra)

            self.linha_galeria.addWidget(self.bt_adicionar_foto_extra)
            self.linha_galeria.addStretch()
            corpo_foto.addLayout(self.linha_galeria)

            self._carregar_galeria_fotos()

        direita.addWidget(cartao_foto)

        # ---------- Resumo ao vivo (coluna direita) ----------

        cartao_resumo, corpo_resumo = self._construir_cartao_secao(
            "Resumo", "Atualiza enquanto você digita.", "bar-chart-2", tokens.SECUNDARIA,
        )

        self.lbl_resumo_preco = QLabel("R$ 0,00")
        self.lbl_resumo_preco.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XXL}px; font-weight:800;
        """)
        self.badge_resumo_promo = Badge("Em promoção", "alerta")
        self.badge_resumo_promo.hide()

        linha_preco_resumo = QHBoxLayout()
        linha_preco_resumo.addWidget(self.lbl_resumo_preco)
        linha_preco_resumo.addStretch()
        linha_preco_resumo.addWidget(self.badge_resumo_promo, 0, Qt.AlignVCenter)
        corpo_resumo.addLayout(linha_preco_resumo)

        self.lbl_resumo_custo = self._linha_resumo(corpo_resumo, "Custo")
        self.lbl_resumo_lucro = self._linha_resumo(corpo_resumo, "Lucro por unidade")
        self.lbl_resumo_margem = self._linha_resumo(corpo_resumo, "Margem")
        self.lbl_resumo_estoque = self._linha_resumo(corpo_resumo, "Estoque")

        direita.addWidget(cartao_resumo)
        direita.addStretch()

        coluna_direita = QWidget()
        coluna_direita.setStyleSheet("background:transparent;")
        coluna_direita.setFixedWidth(_LARGURA_COLUNA_DIREITA)
        coluna_direita.setLayout(direita)

        corpo.addLayout(esquerda, 1)
        corpo.addWidget(coluna_direita, 0, Qt.AlignTop)

        scroll.setWidget(corpo_widget)
        layout.addWidget(scroll, 1)

        # ======================
        # RODAPÉ
        # ======================

        rodape_frame = QFrame()
        rodape_frame.setObjectName("RodapeProduto")
        rodape_frame.setStyleSheet(f"""
            #RodapeProduto {{ background:{tokens.CARD}; border-top:1px solid {tokens.BORDA}; }}
        """)
        rodape = QHBoxLayout(rodape_frame)
        rodape.setContentsMargins(28, 14, 28, 14)
        rodape.setSpacing(10)

        dicas = QLabel("Enter avança  ·  Ctrl+S salva  ·  Esc fecha")
        dicas.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        self.bt_cancelar = BotaoSecundario("Cancelar")
        self.bt_cancelar.setMinimumWidth(140)
        self.bt_cancelar.clicked.connect(self.reject)

        self.bt_salvar = BotaoSucesso(
            "Salvar Alterações" if produto else "Cadastrar Produto", icone_nome="check",
        )
        self.bt_salvar.setMinimumWidth(220)
        self.bt_salvar.clicked.connect(self.salvar)

        rodape.addWidget(dicas)
        rodape.addStretch()
        rodape.addWidget(self.bt_cancelar)
        rodape.addWidget(self.bt_salvar)

        layout.addWidget(rodape_frame)

        QShortcut(QKeySequence("Ctrl+S"), self, self.salvar)

        # resumo ao vivo
        self.preco_venda.valueChanged.connect(self._atualizar_margem)
        self.preco_custo.valueChanged.connect(self._atualizar_margem)
        self.estoque.valueChanged.connect(self._atualizar_margem)
        self.estoque_minimo.valueChanged.connect(self._atualizar_margem)
        self.em_promocao_check.toggled.connect(self._atualizar_margem)
        self.preco_promocional.valueChanged.connect(self._atualizar_margem)

        self._atualizar_estilo_favorito(False)
        self.selecionar_modo("UN")

        # cadastro em MAIUSCULAS (padrao de ERP de loja) -- so' campos
        # de nome; codigo de barras fica como vem do leitor
        forcar_maiusculas(
            self.nome, self.categoria, self.colecao, self.cor, self.tamanho,
        )

        # Enter e' tratado em keyPressEvent (proximo campo / cadastrar)
        # -- sem isso o QDialog "clica" o botao autoDefault da vez
        for botao in self.findChildren(QPushButton):
            botao.setAutoDefault(False)
            botao.setDefault(False)

        if self.produto:
            self.preencher_campos()
            self.codigo_barras.setFocus()
        elif self.produto_pai:
            self._preencher_a_partir_do_pai()
            self.cor.setFocus()
        else:
            self.codigo_barras.setFocus()

        self._atualizar_margem()

    def _atualizar_margem(self, *_):

        venda = self.preco_venda.value()
        custo = self.preco_custo.value()
        promo = self.em_promocao_check.isChecked() and self.preco_promocional.value() > 0
        preco_efetivo = self.preco_promocional.value() if promo else venda

        self.lbl_resumo_preco.setText(formatar_moeda(preco_efetivo))
        self.badge_resumo_promo.setVisible(promo)
        self.lbl_resumo_custo.setText(formatar_moeda(custo) if custo > 0 else "—")

        unidade = {"UN": "un", "KG": "kg", "L": "L"}.get(self.modo_venda, "un")
        estoque = self.estoque.value()
        minimo = self.estoque_minimo.value()
        cor_estoque = tokens.ERRO if estoque <= 0 else (
            tokens.ALERTA if minimo and estoque <= minimo else tokens.TEXTO
        )
        self.lbl_resumo_estoque.setText(f"{estoque} {unidade}")
        self.lbl_resumo_estoque.setStyleSheet(f"""
            background:transparent; color:{cor_estoque};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)

        if preco_efetivo <= 0 or custo <= 0:
            self.lbl_margem.setText("Informe o custo pra ver o lucro e a margem.")
            self.lbl_resumo_lucro.setText("—")
            self.lbl_resumo_margem.setText("—")
            return

        lucro = preco_efetivo - custo
        margem = lucro / preco_efetivo * 100
        cor = tokens.SECUNDARIA_HOVER if lucro > 0 else tokens.ERRO

        self.lbl_margem.setText(
            f"Lucro por unidade: {formatar_moeda(lucro)}  ·  margem {margem:.0f}%"
            + ("  (com o preço promocional)" if promo else "")
        )
        for lbl, texto in (
            (self.lbl_resumo_lucro, formatar_moeda(lucro)),
            (self.lbl_resumo_margem, f"{margem:.0f}%"),
        ):
            lbl.setText(texto)
            lbl.setStyleSheet(f"""
                background:transparent; color:{cor};
                font-size:{tokens.TAMANHO_SM}px; font-weight:800;
            """)

    def keyPressEvent(self, event):
        """Enter anda pelos campos essenciais na ordem em que se
        preenche um cadastro e, no ultimo (estoque), cadastra --
        da' pra fazer tudo sem tirar a mao do teclado."""

        if event.key() not in (Qt.Key_Return, Qt.Key_Enter):
            super().keyPressEvent(event)
            return

        ordem = [
            self.codigo_barras, self.nome, self.categoria,
            self.preco_venda, self.estoque,
        ]

        foco = QApplication.focusWidget()

        if isinstance(foco, QPushButton):
            foco.click()
            return

        # o foco pode estar num filho interno (line edit do spinbox /
        # combo editavel) -- sobe ate' achar o campo da lista
        atual = foco
        while atual is not None and atual not in ordem:
            atual = atual.parentWidget()

        if atual is None:
            self.focusNextChild()
            return

        indice = ordem.index(atual)

        if indice == len(ordem) - 1:
            self.salvar()
            return

        proximo = ordem[indice + 1]
        proximo.setFocus()

        if hasattr(proximo, "selectAll"):
            proximo.selectAll()
        elif hasattr(proximo, "lineEdit") and proximo.lineEdit():
            proximo.lineEdit().selectAll()

    # ==========================================
    # DESCRIÇÃO (limite de 300 caracteres)
    # ==========================================

    def _limitar_descricao(self):

        texto = self.descricao.toPlainText()

        if len(texto) > 300:

            cursor = self.descricao.textCursor()
            posicao = cursor.position()

            self.descricao.blockSignals(True)
            self.descricao.setPlainText(texto[:300])
            cursor.setPosition(min(posicao, 300))
            self.descricao.setTextCursor(cursor)
            self.descricao.blockSignals(False)

            texto = texto[:300]

        self.lbl_contador_descricao.setText(f"{len(texto)}/300")

    # ==========================================
    # PRECO PROMOCIONAL / HISTORICO
    # ==========================================

    def _alternar_promocao(self, marcado):
        self.preco_promocional.setEnabled(marcado)
        self.promocao_inicio.setEnabled(marcado)
        self.promocao_fim.setEnabled(marcado)

    def ver_historico_precos(self):

        if not self.produto:
            return

        dialogo = HistoricoPrecosDialog(
            self.produto["id"], self.produto["nome"], parent=self
        )
        dialogo.exec()

    # ==========================================
    # PREENCHER CAMPOS (EDIÇÃO)
    # ==========================================

    def _preencher_a_partir_do_pai(self):
        """Nova variacao: copia nome/preco/categoria/marca/colecao do
        produto pai como ponto de partida -- so' cor/tamanho/codigo
        ficam pra quem esta cadastrando preencher."""

        pai = self.produto_pai

        self.nome.setText(pai["nome"])
        self.categoria.setCurrentText(pai.get("categoria") or "")

        indice_marca = self.marca.findData(pai.get("marca_id"))
        self.marca.setCurrentIndex(indice_marca if indice_marca >= 0 else 0)

        self.colecao.setText(pai.get("colecao") or "")

        self.preco_custo.setValue(float(pai.get("preco_custo") or 0))
        self.preco_venda.setValue(float(pai.get("preco_venda") or 0))

        self.selecionar_modo(pai.get("unidade") or "UN")

    def preencher_campos(self):

        if not self.produto:
            return

        self.codigo_barras.setText(
            self.produto.get("codigo_barras") or ""
        )
        self.nome.setText(self.produto["nome"])
        self.categoria.setCurrentText(
            self.produto.get("categoria") or ""
        )

        indice_marca = self.marca.findData(self.produto.get("marca_id"))
        self.marca.setCurrentIndex(indice_marca if indice_marca >= 0 else 0)

        self.colecao.setText(self.produto.get("colecao") or "")

        self.cor.setText(self.produto.get("cor") or "")
        self.tamanho.setText(self.produto.get("tamanho") or "")

        self.descricao.setPlainText(
            self.produto.get("descricao") or ""
        )

        self.selecionar_modo(
            self.produto.get("unidade") or "UN"
        )

        self.preco_custo.setValue(
            float(self.produto["preco_custo"])
        )

        self.preco_venda.setValue(
            float(self.produto["preco_venda"])
        )

        self.estoque.setValue(
            self.produto["estoque"]
        )

        self.estoque_minimo.setValue(
            self.produto.get("estoque_minimo", 0)
        )

        self.favorito.setChecked(self.produto.get("favorito", False))

        self.eh_kit_check.setChecked(self.produto.get("eh_kit", False))

        preco_promocional = self.produto.get("preco_promocional")
        self.em_promocao_check.setChecked(preco_promocional is not None)

        if preco_promocional is not None:
            self.preco_promocional.setValue(float(preco_promocional))

        if self.produto.get("promocao_inicio"):
            self.promocao_inicio.setDate(
                QDate.fromString(self.produto["promocao_inicio"], "yyyy-MM-dd")
            )

        if self.produto.get("promocao_fim"):
            self.promocao_fim.setDate(
                QDate.fromString(self.produto["promocao_fim"], "yyyy-MM-dd")
            )

        if self.produto.get("tem_foto"):

            rodar_em_thread(
                self,
                obter_foto_produto,
                self.produto["id"],
                ao_sucesso=self._ao_carregar_foto_sucesso,
            )

    def _ao_carregar_foto_sucesso(self, foto_bytes):
        if foto_bytes:
            self._exibir_imagem(foto_bytes)

    # ==========================================
    # VALIDAR E SALVAR
    # ==========================================

    def salvar(self):

        if self.nome.text().strip() == "":
            QMessageBox.warning(
                self,
                "Aviso",
                "Informe o nome do produto."
            )
            self.nome.setFocus()
            return

        if self.preco_venda.value() <= 0:
            QMessageBox.warning(
                self,
                "Aviso",
                "Informe um preço de venda válido."
            )
            self.preco_venda.setFocus()
            return

        if self.em_promocao_check.isChecked():

            if self.preco_promocional.value() <= 0:
                QMessageBox.warning(
                    self, "Aviso", "Informe um preço promocional válido."
                )
                self.preco_promocional.setFocus()
                return

            if self.promocao_inicio.date() > self.promocao_fim.date():
                QMessageBox.warning(
                    self, "Aviso",
                    "A data \"Válida de\" não pode ser depois de \"Até\"."
                )
                return

        self.accept()

    # ==========================================
    # DADOS
    # ==========================================

    @property
    def dados(self):

        codigo_barras = self.codigo_barras.text().strip() or None

        if self.produto:
            codigo = self.produto["codigo"]
        elif codigo_barras:
            codigo = codigo_barras
        else:
            codigo = ""  # backend gera o proximo codigo interno (0001...)

        foto_base64 = None

        if self.imagem_bytes:
            foto_base64 = base64.b64encode(
                self.imagem_bytes
            ).decode("ascii")

        return {

            "codigo": codigo,

            "codigo_barras": codigo_barras,

            "foto_base64": foto_base64,

            "nome": self.nome.text().strip(),

            "descricao": self.descricao.toPlainText().strip() or None,

            "categoria": self.categoria.currentText().strip() or None,

            "marca_id": self.marca.currentData(),

            "colecao": self.colecao.text().strip() or None,

            "cor": self.cor.text().strip() or None,

            "tamanho": self.tamanho.text().strip() or None,

            "produto_pai_id": self.produto_pai_id,

            "unidade": self.modo_venda,

            "preco_custo": float(
                self.preco_custo.value()
            ),

            "preco_venda": float(
                self.preco_venda.value()
            ),

            "preco_promocional": (
                float(self.preco_promocional.value())
                if self.em_promocao_check.isChecked()
                else None
            ),

            "promocao_inicio": (
                self.promocao_inicio.date().toString("yyyy-MM-dd")
                if self.em_promocao_check.isChecked()
                else None
            ),

            "promocao_fim": (
                self.promocao_fim.date().toString("yyyy-MM-dd")
                if self.em_promocao_check.isChecked()
                else None
            ),

            "estoque": self.estoque.value(),

            "estoque_minimo": self.estoque_minimo.value(),

            "favorito": self.favorito.isChecked(),

            "eh_kit": self.eh_kit_check.isChecked(),
        }
