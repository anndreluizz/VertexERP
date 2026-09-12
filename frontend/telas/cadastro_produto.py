from datetime import datetime

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt, QTimer, QBuffer, QIODevice, QSize
from PySide6.QtGui import QColor, QPixmap

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QInputDialog,
    QFileDialog,
)

import base64

from services.ean_lookup import buscar_produto_externo
from services.categoria_service import listar_categorias, criar_categoria
from telas.gerenciar_categorias import GerenciarCategoriasDialog
from services.produto_service import obter_foto_produto
from design import tokens
from design.icons import icone, icone_pixmap
from design.responsive import tamanho_fixo_seguro
from design.widgets import Card

_TAMANHO_PREVIA = 110

_UNIDADES = [
    ("Unidade (UN)", "UN"),
    ("Quilograma (KG)", "KG"),
    ("Litro (L)", "L"),
]


class CadastroProdutoWindow(QDialog):

    def __init__(self, produto=None):
        super().__init__()

        self.produto = produto
        self.imagem_bytes = None
        self.modo_venda = "UN"

        tamanho_fixo_seguro(self, 1120, 860)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()
        cabecalho.setContentsMargins(30, 24, 30, 20)
        cabecalho.setSpacing(14)

        icone_cabecalho = QLabel()
        icone_cabecalho.setFixedSize(52, 52)
        icone_cabecalho.setAlignment(Qt.AlignCenter)
        icone_cabecalho.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA};
            border-radius:{tokens.RADIUS_MD}px;
        """)
        icone_cabecalho.setPixmap(icone_pixmap("package", cor=tokens.PRIMARIA, tamanho=24))

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(2)

        titulo_texto = "Editar Produto" if produto else "Novo Produto"

        titulo = QLabel(titulo_texto)
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo_texto = (
            "Atualize os dados do produto no sistema."
            if produto else
            "Preencha os dados básicos para cadastrar um novo produto no sistema."
        )

        subtitulo = QLabel(subtitulo_texto)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        self.favorito = QPushButton("Favorito")
        self.favorito.setCheckable(True)
        self.favorito.setCursor(Qt.PointingHandCursor)
        self.favorito.setMinimumHeight(38)
        self.favorito.setToolTip(
            "Produtos favoritos ficam em destaque na busca do PDV"
        )
        self.favorito.toggled.connect(self._atualizar_estilo_favorito)

        bt_fechar = QPushButton()
        bt_fechar.setFixedSize(34, 34)
        bt_fechar.setCursor(Qt.PointingHandCursor)
        bt_fechar.setIcon(icone("x", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        bt_fechar.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:8px; }}
            QPushButton:hover {{ background:{tokens.BORDA}; }}
        """)
        bt_fechar.clicked.connect(self.reject)

        cabecalho.addWidget(icone_cabecalho)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(self.favorito)
        cabecalho.addWidget(bt_fechar)

        layout.addLayout(cabecalho)

        linha_separadora = QFrame()
        linha_separadora.setFixedHeight(1)
        linha_separadora.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        layout.addWidget(linha_separadora)

        # ======================
        # CORPO (2 colunas)
        # ======================

        corpo = QHBoxLayout()
        corpo.setContentsMargins(30, 20, 30, 16)
        corpo.setSpacing(20)

        # ---- coluna esquerda: informações básicas ----

        cartao_info, corpo_info = self._construir_cartao_secao(
            "Informações Básicas",
            "Cadastre as informações principais do produto.",
            "edit-2", tokens.PRIMARIA,
        )

        corpo_info.addWidget(self._rotulo_campo("Código de barras (opcional)"))

        linha_codigo = QHBoxLayout()
        linha_codigo.setSpacing(8)

        self.codigo_barras = QLineEdit()
        self.codigo_barras.setPlaceholderText("Bipar ou digitar o código de barras...")
        self.codigo_barras.setMinimumHeight(42)
        self.codigo_barras.setStyleSheet(self._estilo_input())
        self.codigo_barras.returnPressed.connect(self.buscar_automatico)
        self.codigo_barras.textChanged.connect(
            self.agendar_busca_automatica
        )

        self.timer_busca_automatica = QTimer(self)
        self.timer_busca_automatica.setSingleShot(True)
        self.timer_busca_automatica.timeout.connect(
            lambda: self.buscar_automatico(silencioso=True)
        )

        self.bt_buscar = QPushButton()
        self.bt_buscar.setCursor(Qt.PointingHandCursor)
        self.bt_buscar.setFixedSize(42, 42)
        self.bt_buscar.setToolTip("Consultar produto pelo código (Open Food Facts)")
        self.bt_buscar.setIcon(icone("search", cor="white", tamanho=18))
        self.bt_buscar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.SECUNDARIA};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{
                background:{tokens.SECUNDARIA_HOVER};
            }}
        """)
        self.bt_buscar.clicked.connect(
            lambda: self.buscar_automatico(silencioso=False)
        )

        linha_codigo.addWidget(self.codigo_barras)
        linha_codigo.addWidget(self.bt_buscar)

        corpo_info.addLayout(linha_codigo)

        corpo_info.addWidget(self._rotulo_campo("Nome do produto", obrigatorio=True))

        self.nome = QLineEdit()
        self.nome.setPlaceholderText("Ex.: Coca-Cola Lata 350ml")
        self.nome.setMinimumHeight(42)
        self.nome.setStyleSheet(self._estilo_input())

        corpo_info.addWidget(self.nome)

        corpo_info.addWidget(self._rotulo_campo("Categoria do produto"))

        linha_categoria = QHBoxLayout()
        linha_categoria.setSpacing(8)

        self.categoria = QComboBox()
        self.categoria.setEditable(True)
        self.categoria.setMinimumHeight(42)
        self.categoria.setStyleSheet(self._estilo_input("QComboBox"))
        self._carregar_categorias()

        self.bt_nova_categoria = QPushButton()
        self.bt_nova_categoria.setCursor(Qt.PointingHandCursor)
        self.bt_nova_categoria.setFixedSize(42, 42)
        self.bt_nova_categoria.setToolTip("Criar nova categoria")
        self.bt_nova_categoria.setIcon(icone("plus", cor=tokens.TEXTO, tamanho=16))
        self.bt_nova_categoria.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.FUNDO};
                color:{tokens.TEXTO};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{
                background:{tokens.BORDA};
            }}
        """)
        self.bt_nova_categoria.clicked.connect(self.criar_nova_categoria)

        self.bt_gerenciar_categorias = QPushButton()
        self.bt_gerenciar_categorias.setCursor(Qt.PointingHandCursor)
        self.bt_gerenciar_categorias.setFixedSize(42, 42)
        self.bt_gerenciar_categorias.setToolTip(
            "Gerenciar categorias (editar/excluir)"
        )
        self.bt_gerenciar_categorias.setIcon(
            icone("menu", cor=tokens.TEXTO, tamanho=17)
        )
        self.bt_gerenciar_categorias.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.FUNDO};
                color:{tokens.TEXTO};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{
                background:{tokens.BORDA};
            }}
        """)
        self.bt_gerenciar_categorias.clicked.connect(
            self.gerenciar_categorias
        )

        linha_categoria.addWidget(self.categoria)
        linha_categoria.addWidget(self.bt_nova_categoria)
        linha_categoria.addWidget(self.bt_gerenciar_categorias)

        corpo_info.addLayout(linha_categoria)

        corpo_info.addWidget(self._rotulo_campo("Descrição (opcional)"))

        self.descricao = QPlainTextEdit()
        self.descricao.setPlaceholderText(
            "Ex.: refrigerante, embalagem, sabor, observações..."
        )
        self.descricao.setFixedHeight(88)
        self.descricao.setStyleSheet(f"""
            QPlainTextEdit {{
                border: 1px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 8px 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QPlainTextEdit:focus {{ border: 1px solid {tokens.SECUNDARIA}; }}
        """)
        self.descricao.textChanged.connect(self._limitar_descricao)

        corpo_info.addWidget(self.descricao)

        self.lbl_contador_descricao = QLabel("0/300")
        self.lbl_contador_descricao.setAlignment(Qt.AlignRight)
        self.lbl_contador_descricao.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)
        corpo_info.addWidget(self.lbl_contador_descricao)

        corpo_info.addStretch()

        # ---- coluna direita: valores + foto ----

        direita = QVBoxLayout()
        direita.setSpacing(20)

        cartao_valores, corpo_valores = self._construir_cartao_secao(
            "Valores e Disponibilidade",
            "Defina o preço, custos e controle de estoque.",
            "dollar-sign", tokens.SECUNDARIA,
        )

        linha_preco_modo = QHBoxLayout()
        linha_preco_modo.setSpacing(16)

        col_preco = QVBoxLayout()
        col_preco.setSpacing(6)
        col_preco.addWidget(self._rotulo_campo("Preço de venda (R$)", obrigatorio=True))
        self.preco_venda = QDoubleSpinBox()
        self.preco_venda.setMaximum(999999.99)
        self.preco_venda.setDecimals(2)
        self.preco_venda.setPrefix("R$ ")
        self.preco_venda.setMinimumHeight(42)
        self.preco_venda.setStyleSheet(self._estilo_input("QDoubleSpinBox"))
        col_preco.addWidget(self.preco_venda)

        col_modo = QVBoxLayout()
        col_modo.setSpacing(6)
        col_modo.addWidget(self._rotulo_campo("Modo de venda"))

        linha_modo = QHBoxLayout()
        linha_modo.setSpacing(4)

        self.botoes_modo = {}

        for rotulo, valor in [
            ("UNID", "UN"), ("PESO", "KG"), ("LITRO", "L"),
        ]:
            bt = QPushButton(rotulo)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setCheckable(True)
            bt.setMinimumHeight(42)
            bt.clicked.connect(
                lambda checked, v=valor: self.selecionar_modo(v)
            )
            self.botoes_modo[valor] = bt
            linha_modo.addWidget(bt)

        col_modo.addLayout(linha_modo)

        linha_preco_modo.addLayout(col_preco)
        linha_preco_modo.addLayout(col_modo)

        corpo_valores.addLayout(linha_preco_modo)

        linha_custo_estoque = QHBoxLayout()
        linha_custo_estoque.setSpacing(16)

        col_custo = QVBoxLayout()
        col_custo.setSpacing(6)
        col_custo.addWidget(self._rotulo_campo("Custo de compra (R$)"))
        self.preco_custo = QDoubleSpinBox()
        self.preco_custo.setMaximum(999999.99)
        self.preco_custo.setDecimals(2)
        self.preco_custo.setPrefix("R$ ")
        self.preco_custo.setMinimumHeight(42)
        self.preco_custo.setStyleSheet(self._estilo_input("QDoubleSpinBox"))
        col_custo.addWidget(self.preco_custo)

        col_estoque = QVBoxLayout()
        col_estoque.setSpacing(6)
        col_estoque.addWidget(self._rotulo_campo("Estoque inicial"))
        self.estoque = QSpinBox()
        self.estoque.setMaximum(999999)
        self.estoque.setMinimumHeight(42)
        self.estoque.setStyleSheet(self._estilo_input("QSpinBox"))
        col_estoque.addWidget(self.estoque)

        linha_custo_estoque.addLayout(col_custo)
        linha_custo_estoque.addLayout(col_estoque)

        corpo_valores.addLayout(linha_custo_estoque)

        linha_minimo_unidade = QHBoxLayout()
        linha_minimo_unidade.setSpacing(16)

        col_estoque_minimo = QVBoxLayout()
        col_estoque_minimo.setSpacing(6)
        col_estoque_minimo.addWidget(self._rotulo_campo("Estoque mínimo (alerta)"))
        self.estoque_minimo = QSpinBox()
        self.estoque_minimo.setMaximum(999999)
        self.estoque_minimo.setMinimumHeight(42)
        self.estoque_minimo.setStyleSheet(self._estilo_input("QSpinBox"))
        col_estoque_minimo.addWidget(self.estoque_minimo)

        col_unidade = QVBoxLayout()
        col_unidade.setSpacing(6)
        col_unidade.addWidget(self._rotulo_campo("Unidade de medida"))
        self.unidade_medida = QComboBox()
        for rotulo, valor in _UNIDADES:
            self.unidade_medida.addItem(rotulo, valor)
        self.unidade_medida.setEnabled(False)
        self.unidade_medida.setToolTip("Acompanha o Modo de Venda selecionado acima")
        self.unidade_medida.setMinimumHeight(42)
        self.unidade_medida.setStyleSheet(self._estilo_input("QComboBox"))
        col_unidade.addWidget(self.unidade_medida)

        linha_minimo_unidade.addLayout(col_estoque_minimo)
        linha_minimo_unidade.addLayout(col_unidade)

        corpo_valores.addLayout(linha_minimo_unidade)

        banner_info = QLabel(
            "Quando o estoque atingir o mínimo, o produto será exibido "
            "no alerta de estoque."
        )
        banner_info.setWordWrap(True)
        banner_info.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA_HOVER};
            font-size:{tokens.TAMANHO_SM}px; border-radius:{tokens.RADIUS_SM}px;
            padding:10px 14px;
        """)
        corpo_valores.addWidget(banner_info)

        cartao_foto, corpo_foto = self._construir_cartao_secao(
            "Foto do produto",
            "Adicione uma imagem para facilitar a identificação.",
            "package", tokens.PRIMARIA,
        )

        linha_foto = QHBoxLayout()
        linha_foto.setSpacing(14)

        self.bt_adicionar_imagem = QPushButton(
            "Clique para adicionar uma imagem\nPNG, JPG ou WEBP (máx. 5MB)"
        )
        self.bt_adicionar_imagem.setCursor(Qt.PointingHandCursor)
        self.bt_adicionar_imagem.setMinimumHeight(_TAMANHO_PREVIA)
        self.bt_adicionar_imagem.setIcon(
            icone("package", cor=tokens.TEXTO_SECUNDARIO, tamanho=24)
        )
        self.bt_adicionar_imagem.setIconSize(QSize(24, 24))
        self.bt_adicionar_imagem.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.FUNDO}; border:1.5px dashed {tokens.BORDA_FORTE};
                border-radius:{tokens.RADIUS_MD}px; color:{tokens.TEXTO_SECUNDARIO};
                font-weight:700; font-size:{tokens.TAMANHO_SM}px; padding:14px;
            }}
            QPushButton:hover {{ background:{tokens.BORDA}; }}
        """)
        self.bt_adicionar_imagem.clicked.connect(
            self.adicionar_imagem
        )

        col_previa = QVBoxLayout()
        col_previa.setSpacing(6)

        self.lbl_foto = QLabel()
        self.lbl_foto.setFixedSize(_TAMANHO_PREVIA, _TAMANHO_PREVIA)
        self.lbl_foto.setAlignment(Qt.AlignCenter)
        self.lbl_foto.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_MD}px;
        """)
        self.lbl_foto.setPixmap(
            icone_pixmap("package", cor=tokens.TEXTO_TERCIARIO, tamanho=32)
        )

        lbl_previa_legenda = QLabel("Pré-visualização")
        lbl_previa_legenda.setAlignment(Qt.AlignCenter)
        lbl_previa_legenda.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_previa.addWidget(self.lbl_foto)
        col_previa.addWidget(lbl_previa_legenda)

        linha_foto.addWidget(self.bt_adicionar_imagem, stretch=1)
        linha_foto.addLayout(col_previa)

        corpo_foto.addLayout(linha_foto)

        direita.addWidget(cartao_valores)
        direita.addWidget(cartao_foto)

        corpo.addWidget(cartao_info, 1)
        corpo.addLayout(direita, 1)

        layout.addLayout(corpo)

        # ======================
        # RODAPÉ
        # ======================

        rodape = QHBoxLayout()
        rodape.setContentsMargins(30, 16, 30, 24)
        rodape.setSpacing(10)

        self.bt_cancelar = QPushButton("Cancelar")
        self.bt_cancelar.setCursor(Qt.PointingHandCursor)
        self.bt_cancelar.setMinimumHeight(46)
        self.bt_cancelar.setIcon(icone("x", cor=tokens.TEXTO_SECUNDARIO, tamanho=15))
        self.bt_cancelar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; color:{tokens.TEXTO};
                border:1.5px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                font-weight:700; padding:0 18px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        self.bt_cancelar.clicked.connect(self.reject)

        texto_salvar = "Salvar Alterações" if produto else "Cadastrar Produto"

        self.bt_salvar = QPushButton(texto_salvar)
        self.bt_salvar.setCursor(Qt.PointingHandCursor)
        self.bt_salvar.setMinimumHeight(46)
        self.bt_salvar.setMinimumWidth(220)
        self.bt_salvar.setIcon(icone("check", cor="white", tamanho=16))
        self.bt_salvar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.SECUNDARIA};
                color:{tokens.TEXTO_CLARO};
                font-weight:700;
                border-radius:{tokens.RADIUS_SM}px;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background:{tokens.SECUNDARIA_HOVER};
            }}
        """)
        self.bt_salvar.clicked.connect(self.salvar)

        rodape.addWidget(self.bt_cancelar)
        rodape.addStretch()
        rodape.addWidget(self.bt_salvar)

        layout.addLayout(rodape)

        self._atualizar_estilo_favorito(False)
        self.selecionar_modo("UN")

        if self.produto:
            self.preencher_campos()
            self.codigo_barras.setFocus()
        else:
            self.codigo_barras.setFocus()

    # ==========================================
    # HELPERS DE ESTILO
    # ==========================================

    def _construir_cartao_secao(self, titulo, subtitulo, icone_nome, cor):
        """Card com cabeçalho (ícone colorido + título + subtítulo) e um
        corpo (QVBoxLayout) pra quem chama encaixar os campos --
        mesma linguagem visual do SecaoCard usado no Dashboard, só que
        com subtítulo, que aqui é essencial pra explicar cada bloco."""

        card = Card()

        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        cabecalho_secao = QHBoxLayout()
        cabecalho_secao.setSpacing(12)

        icone_secao = QLabel()
        icone_secao.setFixedSize(36, 36)
        icone_secao.setAlignment(Qt.AlignCenter)
        cor_rgb = QColor(cor)
        icone_secao.setStyleSheet(f"""
            background: rgba({cor_rgb.red()}, {cor_rgb.green()}, {cor_rgb.blue()}, 0.12);
            border-radius:{tokens.RADIUS_SM}px;
        """)
        icone_secao.setPixmap(icone_pixmap(icone_nome, cor=cor, tamanho=17))

        col_titulo_secao = QVBoxLayout()
        col_titulo_secao.setSpacing(1)

        titulo_lbl = QLabel(titulo)
        titulo_lbl.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:800;
        """)

        subtitulo_lbl = QLabel(subtitulo)
        subtitulo_lbl.setWordWrap(True)
        subtitulo_lbl.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_titulo_secao.addWidget(titulo_lbl)
        col_titulo_secao.addWidget(subtitulo_lbl)

        cabecalho_secao.addWidget(icone_secao)
        cabecalho_secao.addLayout(col_titulo_secao, 1)

        layout.addLayout(cabecalho_secao)

        corpo_secao = QVBoxLayout()
        corpo_secao.setSpacing(12)
        layout.addLayout(corpo_secao)

        return card, corpo_secao

    def _rotulo_campo(self, texto, obrigatorio=False):

        sufixo = f' <span style="color:{tokens.ERRO};">*</span>' if obrigatorio else ""

        lbl = QLabel(f"{texto}{sufixo}")
        lbl.setTextFormat(Qt.RichText)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:700; color:{tokens.TEXTO};
        """)
        return lbl

    def _estilo_input(self, widget="QLineEdit"):
        return f"""
            {widget} {{
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px;
                font-size: {tokens.TAMANHO_MD}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            {widget}:focus {{
                border: 1px solid {tokens.SECUNDARIA};
            }}
        """

    def _atualizar_estilo_favorito(self, marcado):

        self.favorito.setStyleSheet(f"""
            QPushButton {{
                background: {tokens.ALERTA_CLARO if marcado else tokens.CARD};
                color: {tokens.ALERTA_TEXTO};
                border: 1.5px solid {tokens.ALERTA if marcado else tokens.BORDA};
                border-radius: {tokens.RADIUS_PILL}px;
                padding: 0 16px; font-weight: 700; font-size: {tokens.TAMANHO_SM}px;
            }}
            QPushButton:hover {{ background: {tokens.ALERTA_CLARO}; }}
        """)

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
    # CATEGORIAS
    # ==========================================

    def _carregar_categorias(self):

        # preserva o que ja estava selecionado/digitado -- sem isso,
        # recarregar a lista (ex.: depois de fechar "Gerenciar
        # categorias") apagava a categoria que o usuario ja tinha
        # escolhido pro produto em edicao (mesmo padrao ja usado em
        # cadastro_despesa.py pro mesmo tipo de combobox)
        selecionada = self.categoria.currentText()

        categorias = listar_categorias()

        self.categoria.clear()

        for c in categorias:
            if c.get("ativo", True):
                self.categoria.addItem(c["nome"])

        self.categoria.setCurrentText(selecionada)

    def criar_nova_categoria(self):

        nome, ok = QInputDialog.getText(
            self,
            "Nova Categoria",
            "Nome da nova categoria:"
        )

        if not ok or not nome.strip():
            return

        nome = nome.strip()

        response = criar_categoria(nome)

        if response.status_code in (200, 201):

            if self.categoria.findText(nome) < 0:
                self.categoria.addItem(nome)

            self.categoria.setCurrentText(nome)

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def gerenciar_categorias(self):

        dialogo = GerenciarCategoriasDialog(parent=self)
        dialogo.exec()

        self._carregar_categorias()

    # ==========================================
    # MODO DE VENDA (UNID / PESO / LITRO)
    # ==========================================

    def selecionar_modo(self, valor):

        self.modo_venda = valor

        for chave, botao in self.botoes_modo.items():

            selecionado = chave == valor
            botao.setChecked(selecionado)

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.SIDEBAR if selecionado else tokens.FUNDO};
                    color: {tokens.TEXTO_CLARO if selecionado else tokens.TEXTO};
                    border-radius: {tokens.RADIUS_SM}px;
                    font-weight: bold;
                    font-size: {tokens.TAMANHO_XS}px;
                }}
                QPushButton:hover {{
                    background: {tokens.SIDEBAR_HOVER if selecionado else tokens.BORDA};
                }}
            """)

        indice_unidade = self.unidade_medida.findData(valor)
        if indice_unidade >= 0:
            self.unidade_medida.setCurrentIndex(indice_unidade)

    # ==========================================
    # BUSCA AUTOMÁTICA PELO CÓDIGO DE BARRAS
    # ==========================================

    def agendar_busca_automatica(self, texto):

        self.timer_busca_automatica.stop()

        # so dispara sozinho com tamanho de codigo de barras de
        # verdade, pra nao ficar buscando a cada digito
        if len(texto.strip()) >= 8:
            self.timer_busca_automatica.start(400)

    def buscar_automatico(self, silencioso=False):

        codigo = self.codigo_barras.text().strip()

        if not codigo:
            if not silencioso:
                QMessageBox.information(
                    self,
                    "Buscar produto",
                    "Informe um código de barras para buscar."
                )
            return

        self.bt_buscar.setEnabled(False)
        QApplication.processEvents()

        resultado = buscar_produto_externo(codigo)

        self.bt_buscar.setEnabled(True)

        if resultado is None:

            if not silencioso:
                QMessageBox.information(
                    self,
                    "Buscar produto",
                    "Produto não encontrado na base pública "
                    "(Open Food Facts). Cadastre os dados manualmente."
                )
            return

        self.nome.setText(resultado["nome"])

        if resultado["imagem_bytes"]:

            self.imagem_bytes = resultado["imagem_bytes"]
            self._exibir_imagem(self.imagem_bytes)

    def adicionar_imagem(self):

        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem",
            "",
            "Imagens (*.png *.jpg *.jpeg *.bmp *.webp)",
        )

        if not caminho:
            return

        imagem_comprimida = self._comprimir_imagem(caminho)

        if imagem_comprimida is None:
            QMessageBox.warning(
                self,
                "Imagem inválida",
                "Não foi possível abrir essa imagem."
            )
            return

        self.imagem_bytes = imagem_comprimida

        self._exibir_imagem(self.imagem_bytes)

    def _comprimir_imagem(self, caminho, lado_maximo=640, qualidade=82):
        """Reduz a foto pro tamanho real de exibição (miniatura na
        lista de produtos, no PDV etc.) antes de mandar pro backend --
        sem isso, uma foto tirada direto do celular (facilmente
        3-5 MB) ia inteira pro banco, e a lista de produtos (que
        carrega uma foto por linha) ficava visivelmente lenta pra
        abrir. JPEG a essa qualidade fica imperceptível numa
        miniatura de ~50px e ocupa uma fração do tamanho original."""

        pixmap = QPixmap(caminho)

        if pixmap.isNull():
            return None

        if pixmap.width() > lado_maximo or pixmap.height() > lado_maximo:
            pixmap = pixmap.scaled(
                lado_maximo, lado_maximo,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )

        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "JPEG", qualidade)

        return bytes(buffer.data())

    def _exibir_imagem(self, imagem_bytes):

        pixmap = QPixmap()
        pixmap.loadFromData(imagem_bytes)

        if pixmap.isNull():
            QMessageBox.warning(
                self,
                "Imagem inválida",
                "Não foi possível abrir essa imagem."
            )
            return

        self.lbl_foto.setPixmap(
            pixmap.scaled(
                _TAMANHO_PREVIA, _TAMANHO_PREVIA,
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
        )

    # ==========================================
    # PREENCHER CAMPOS (EDIÇÃO)
    # ==========================================

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

        if self.produto.get("tem_foto"):

            foto_bytes = obter_foto_produto(self.produto["id"])

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
            codigo = "PROD-" + datetime.now().strftime(
                "%Y%m%d%H%M%S%f"
            )

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

            "unidade": self.modo_venda,

            "preco_custo": float(
                self.preco_custo.value()
            ),

            "preco_venda": float(
                self.preco_venda.value()
            ),

            "estoque": self.estoque.value(),

            "estoque_minimo": self.estoque_minimo.value(),

            "favorito": self.favorito.isChecked(),
        }
