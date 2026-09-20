from datetime import datetime

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt, QTimer, QBuffer, QIODevice, QSize, QDate
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
    QCheckBox,
    QDateEdit,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QInputDialog,
    QFileDialog,
    QTableWidgetItem,
)

import base64

from services.ean_lookup import buscar_produto_externo
from services.categoria_service import listar_categorias, criar_categoria
from services.marca_service import listar_marcas, criar_marca
from telas.gerenciar_categorias import GerenciarCategoriasDialog
from telas.gerenciar_marcas import GerenciarMarcasDialog
from telas.historico_precos import HistoricoPrecosDialog
from services.produto_service import (
    obter_foto_produto,
    listar_produtos,
    cadastrar_produto,
    listar_variacoes,
)
from services.produto_foto_service import (
    listar_fotos_produto,
    obter_imagem_foto,
    adicionar_foto_produto,
    remover_foto_produto,
    marcar_foto_principal,
)
from services.kit_item_service import (
    listar_itens_kit,
    adicionar_item_kit,
    remover_item_kit,
)
from services.worker import rodar_em_thread
from widgets.dialogs.pesquisa_window import PesquisaWindow
from widgets.tables.standard_table import StandardTable
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


def _criar_categoria_com_nome(nome):
    """Roda na worker thread -- o nome viaja junto com a resposta (nao
    da pra usar lambda/closure como callback, ver services/worker.py)."""
    return criar_categoria(nome), nome


def _criar_marca_com_nome(nome):
    """Mesmo motivo de _criar_categoria_com_nome."""
    return criar_marca(nome), nome


def _buscar_produto_externo_com_flag(codigo, silencioso):
    """Roda na worker thread -- 'silencioso' viaja junto com o
    resultado pelo mesmo motivo de _criar_categoria_com_nome."""
    return buscar_produto_externo(codigo), silencioso


def _buscar_miniatura_com_info(produto_id, foto):
    """Roda na worker thread -- 'foto' (os metadados, id/ordem/
    principal) viaja junto com os bytes da imagem baixada, mesmo
    motivo de _criar_categoria_com_nome."""
    return foto, obter_imagem_foto(produto_id, foto["id"])


class CadastroProdutoWindow(QDialog):

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

        if produto:
            titulo_texto = "Editar Produto"
        elif produto_pai:
            titulo_texto = f"Nova Variação de \"{produto_pai['nome']}\""
        else:
            titulo_texto = "Novo Produto"

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
        bt_fechar.setToolTip("Fechar")
        bt_fechar.setAccessibleName("Fechar")
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
        self.bt_buscar.setAccessibleName("Consultar produto pelo código")
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
        self.bt_nova_categoria.setAccessibleName("Criar nova categoria")
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
        self.bt_gerenciar_categorias.setAccessibleName(
            "Gerenciar categorias"
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

        corpo_info.addWidget(self._rotulo_campo("Marca (opcional)"))

        linha_marca = QHBoxLayout()
        linha_marca.setSpacing(8)

        self.marca = QComboBox()
        self.marca.setEditable(False)
        self.marca.setMinimumHeight(42)
        self.marca.setStyleSheet(self._estilo_input("QComboBox"))
        self._carregar_marcas()

        self.bt_nova_marca = QPushButton()
        self.bt_nova_marca.setCursor(Qt.PointingHandCursor)
        self.bt_nova_marca.setFixedSize(42, 42)
        self.bt_nova_marca.setToolTip("Criar nova marca")
        self.bt_nova_marca.setAccessibleName("Criar nova marca")
        self.bt_nova_marca.setIcon(icone("plus", cor=tokens.TEXTO, tamanho=16))
        self.bt_nova_marca.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.FUNDO};
                color:{tokens.TEXTO};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{
                background:{tokens.BORDA};
            }}
        """)
        self.bt_nova_marca.clicked.connect(self.criar_nova_marca)

        self.bt_gerenciar_marcas = QPushButton()
        self.bt_gerenciar_marcas.setCursor(Qt.PointingHandCursor)
        self.bt_gerenciar_marcas.setFixedSize(42, 42)
        self.bt_gerenciar_marcas.setToolTip("Gerenciar marcas (editar/excluir)")
        self.bt_gerenciar_marcas.setAccessibleName("Gerenciar marcas")
        self.bt_gerenciar_marcas.setIcon(
            icone("menu", cor=tokens.TEXTO, tamanho=17)
        )
        self.bt_gerenciar_marcas.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.FUNDO};
                color:{tokens.TEXTO};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{
                background:{tokens.BORDA};
            }}
        """)
        self.bt_gerenciar_marcas.clicked.connect(self.gerenciar_marcas)

        linha_marca.addWidget(self.marca)
        linha_marca.addWidget(self.bt_nova_marca)
        linha_marca.addWidget(self.bt_gerenciar_marcas)

        corpo_info.addLayout(linha_marca)

        corpo_info.addWidget(self._rotulo_campo("Coleção (opcional)"))

        self.colecao = QLineEdit()
        self.colecao.setPlaceholderText("Ex.: Verão 2026, Linha Premium...")
        self.colecao.setMinimumHeight(42)
        self.colecao.setStyleSheet(self._estilo_input())

        corpo_info.addWidget(self.colecao)

        linha_variacao = QHBoxLayout()
        linha_variacao.setSpacing(12)

        col_cor = QVBoxLayout()
        col_cor.setSpacing(6)
        col_cor.addWidget(self._rotulo_campo("Cor (opcional)"))
        self.cor = QLineEdit()
        self.cor.setPlaceholderText("Ex.: Azul")
        self.cor.setMinimumHeight(42)
        self.cor.setStyleSheet(self._estilo_input())
        col_cor.addWidget(self.cor)

        col_tamanho = QVBoxLayout()
        col_tamanho.setSpacing(6)
        col_tamanho.addWidget(self._rotulo_campo("Tamanho (opcional)"))
        self.tamanho = QLineEdit()
        self.tamanho.setPlaceholderText("Ex.: P, M, 42...")
        self.tamanho.setMinimumHeight(42)
        self.tamanho.setStyleSheet(self._estilo_input())
        col_tamanho.addWidget(self.tamanho)

        linha_variacao.addLayout(col_cor)
        linha_variacao.addLayout(col_tamanho)

        corpo_info.addLayout(linha_variacao)

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

        linha_promocao_titulo = QHBoxLayout()
        linha_promocao_titulo.setSpacing(8)

        self.em_promocao_check = QCheckBox("Preço promocional")
        self.em_promocao_check.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO}; "
            f"font-weight:700; font-size:{tokens.TAMANHO_SM}px;"
        )
        self.em_promocao_check.toggled.connect(self._alternar_promocao)
        linha_promocao_titulo.addWidget(self.em_promocao_check)
        linha_promocao_titulo.addStretch()

        self.bt_historico_precos = QPushButton("Histórico de preços")
        self.bt_historico_precos.setCursor(Qt.PointingHandCursor)
        self.bt_historico_precos.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{tokens.SECUNDARIA};
                font-weight:700; font-size:{tokens.TAMANHO_SM}px;
                border:none; padding:0;
            }}
            QPushButton:hover {{ color:{tokens.SECUNDARIA_HOVER}; }}
        """)
        self.bt_historico_precos.clicked.connect(self.ver_historico_precos)
        self.bt_historico_precos.setVisible(self.produto is not None)
        linha_promocao_titulo.addWidget(self.bt_historico_precos)

        corpo_valores.addLayout(linha_promocao_titulo)

        linha_promocao = QHBoxLayout()
        linha_promocao.setSpacing(16)

        col_preco_promo = QVBoxLayout()
        col_preco_promo.setSpacing(6)
        col_preco_promo.addWidget(self._rotulo_campo("Preço promocional (R$)"))
        self.preco_promocional = QDoubleSpinBox()
        self.preco_promocional.setMaximum(999999.99)
        self.preco_promocional.setDecimals(2)
        self.preco_promocional.setPrefix("R$ ")
        self.preco_promocional.setMinimumHeight(42)
        self.preco_promocional.setStyleSheet(self._estilo_input("QDoubleSpinBox"))
        col_preco_promo.addWidget(self.preco_promocional)

        col_promo_inicio = QVBoxLayout()
        col_promo_inicio.setSpacing(6)
        col_promo_inicio.addWidget(self._rotulo_campo("Válida de"))
        self.promocao_inicio = QDateEdit()
        self.promocao_inicio.setCalendarPopup(True)
        self.promocao_inicio.setDisplayFormat("dd/MM/yyyy")
        self.promocao_inicio.setDate(QDate.currentDate())
        self.promocao_inicio.setMinimumHeight(42)
        self.promocao_inicio.setStyleSheet(self._estilo_input("QDateEdit"))
        col_promo_inicio.addWidget(self.promocao_inicio)

        col_promo_fim = QVBoxLayout()
        col_promo_fim.setSpacing(6)
        col_promo_fim.addWidget(self._rotulo_campo("Até"))
        self.promocao_fim = QDateEdit()
        self.promocao_fim.setCalendarPopup(True)
        self.promocao_fim.setDisplayFormat("dd/MM/yyyy")
        self.promocao_fim.setDate(QDate.currentDate().addDays(7))
        self.promocao_fim.setMinimumHeight(42)
        self.promocao_fim.setStyleSheet(self._estilo_input("QDateEdit"))
        col_promo_fim.addWidget(self.promocao_fim)

        linha_promocao.addLayout(col_preco_promo)
        linha_promocao.addLayout(col_promo_inicio)
        linha_promocao.addLayout(col_promo_fim)

        corpo_valores.addLayout(linha_promocao)

        self._alternar_promocao(False)

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

        # ---- galeria de fotos adicionais -- so' funciona editando um
        # produto ja existente, porque anexar foto extra usa
        # POST /produtos/{id}/fotos, que precisa de um id que produto
        # novo ainda nao tem (a foto principal acima continua indo
        # pelo caminho de sempre, funciona pra produto novo tambem) ----
        if self.produto:

            lbl_galeria = QLabel(
                "Fotos adicionais (clique na estrela pra tornar principal)"
            )
            lbl_galeria.setWordWrap(True)
            lbl_galeria.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_XS}px; font-weight:700;
                margin-top:8px;
            """)
            corpo_foto.addWidget(lbl_galeria)

            self.linha_galeria = QHBoxLayout()
            self.linha_galeria.setSpacing(8)

            self.bt_adicionar_foto_extra = QPushButton()
            self.bt_adicionar_foto_extra.setFixedSize(56, 56)
            self.bt_adicionar_foto_extra.setCursor(Qt.PointingHandCursor)
            self.bt_adicionar_foto_extra.setToolTip("Adicionar mais uma foto")
            self.bt_adicionar_foto_extra.setAccessibleName(
                "Adicionar mais uma foto"
            )
            self.bt_adicionar_foto_extra.setIcon(
                icone("plus", cor=tokens.TEXTO_SECUNDARIO, tamanho=18)
            )
            self.bt_adicionar_foto_extra.setStyleSheet(f"""
                QPushButton {{
                    background:{tokens.FUNDO}; border:1.5px dashed {tokens.BORDA_FORTE};
                    border-radius:{tokens.RADIUS_SM}px;
                }}
                QPushButton:hover {{ background:{tokens.BORDA}; }}
            """)
            self.bt_adicionar_foto_extra.clicked.connect(
                self.adicionar_foto_extra
            )

            self.linha_galeria.addWidget(self.bt_adicionar_foto_extra)
            self.linha_galeria.addStretch()

            corpo_foto.addLayout(self.linha_galeria)

            self._carregar_galeria_fotos()

        cartao_kit, corpo_kit = self._construir_cartao_secao(
            "Kit / Combo",
            "Venda vários produtos como um só -- o estoque baixado é "
            "o dos componentes, não o do kit.",
            "package", tokens.ALERTA,
        )

        self.eh_kit_check = QCheckBox("Este produto é um kit/combo")
        self.eh_kit_check.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO}; "
            f"font-weight:700; font-size:{tokens.TAMANHO_SM}px;"
        )
        self.eh_kit_check.toggled.connect(self._alternar_kit)
        corpo_kit.addWidget(self.eh_kit_check)

        self.painel_kit = QWidget()
        layout_painel_kit = QVBoxLayout(self.painel_kit)
        layout_painel_kit.setContentsMargins(0, 0, 0, 0)
        layout_painel_kit.setSpacing(8)

        self.tabela_kit = StandardTable(["Componente", "Quantidade"])
        self.tabela_kit.setMaximumHeight(140)
        layout_painel_kit.addWidget(self.tabela_kit)

        linha_botoes_kit = QHBoxLayout()
        linha_botoes_kit.setSpacing(8)

        self.bt_adicionar_componente = QPushButton("Adicionar componente")
        self.bt_adicionar_componente.setCursor(Qt.PointingHandCursor)
        self.bt_adicionar_componente.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.FUNDO}; color:{tokens.TEXTO};
                border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px; padding:8px 14px;
            }}
            QPushButton:hover {{ background:{tokens.BORDA}; }}
        """)
        self.bt_adicionar_componente.clicked.connect(
            self.adicionar_componente_kit
        )
        linha_botoes_kit.addWidget(self.bt_adicionar_componente)

        self.bt_remover_componente = QPushButton("Remover selecionado")
        self.bt_remover_componente.setCursor(Qt.PointingHandCursor)
        self.bt_remover_componente.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.ERRO_CLARO}; color:{tokens.ERRO};
                border-radius:{tokens.RADIUS_SM}px; padding:8px 14px;
            }}
            QPushButton:hover {{ background:{tokens.ERRO}; color:{tokens.TEXTO_CLARO}; }}
        """)
        self.bt_remover_componente.clicked.connect(
            self.remover_componente_kit
        )
        linha_botoes_kit.addWidget(self.bt_remover_componente)
        linha_botoes_kit.addStretch()

        layout_painel_kit.addLayout(linha_botoes_kit)

        corpo_kit.addWidget(self.painel_kit)

        if self.produto is None:
            aviso_kit = QLabel(
                "Salve o produto primeiro pra poder adicionar os "
                "componentes do kit."
            )
            aviso_kit.setWordWrap(True)
            aviso_kit.setStyleSheet(
                f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; "
                f"font-size:{tokens.TAMANHO_XS}px;"
            )
            corpo_kit.addWidget(aviso_kit)
            self.painel_kit.setVisible(False)
        else:
            self.kit_itens = []
            self._carregar_itens_kit()

        self._alternar_kit(False)

        if self._pode_ter_variacoes:

            cartao_variacoes, corpo_variacoes = self._construir_cartao_secao(
                "Variações",
                "Mesmo produto em cores/tamanhos diferentes, cada um "
                "com código e estoque próprios.",
                "package", tokens.SECUNDARIA,
            )

            self.tabela_variacoes = StandardTable(
                ["Nome", "Cor", "Tamanho", "Estoque"]
            )
            self.tabela_variacoes.setMaximumHeight(140)
            corpo_variacoes.addWidget(self.tabela_variacoes)

            self.bt_nova_variacao = QPushButton("Nova variação")
            self.bt_nova_variacao.setCursor(Qt.PointingHandCursor)
            self.bt_nova_variacao.setStyleSheet(f"""
                QPushButton {{
                    background:{tokens.FUNDO}; color:{tokens.TEXTO};
                    border:1px solid {tokens.BORDA};
                    border-radius:{tokens.RADIUS_SM}px; padding:8px 14px;
                }}
                QPushButton:hover {{ background:{tokens.BORDA}; }}
            """)
            self.bt_nova_variacao.clicked.connect(self.nova_variacao)
            corpo_variacoes.addWidget(self.bt_nova_variacao)

            if self.produto is None:
                aviso_variacoes = QLabel(
                    "Salve o produto primeiro pra poder cadastrar "
                    "variações."
                )
                aviso_variacoes.setWordWrap(True)
                aviso_variacoes.setStyleSheet(
                    f"background:transparent; "
                    f"color:{tokens.TEXTO_TERCIARIO}; "
                    f"font-size:{tokens.TAMANHO_XS}px;"
                )
                corpo_variacoes.addWidget(aviso_variacoes)
                self.bt_nova_variacao.setEnabled(False)
            else:
                self._carregar_variacoes()

            direita.addWidget(cartao_variacoes)

        direita.addWidget(cartao_valores)
        direita.addWidget(cartao_kit)
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
        elif self.produto_pai:
            self._preencher_a_partir_do_pai()
            self.cor.setFocus()
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
        self._categoria_selecionada_pendente = self.categoria.currentText()

        rodar_em_thread(
            self,
            listar_categorias,
            ao_sucesso=self._ao_carregar_categorias_sucesso,
        )

    def _ao_carregar_categorias_sucesso(self, categorias):

        self.categoria.clear()

        for c in categorias:
            if c.get("ativo", True):
                self.categoria.addItem(c["nome"])

        self.categoria.setCurrentText(self._categoria_selecionada_pendente)

    def criar_nova_categoria(self):

        nome, ok = QInputDialog.getText(
            self,
            "Nova Categoria",
            "Nome da nova categoria:"
        )

        if not ok or not nome.strip():
            return

        nome = nome.strip()

        rodar_em_thread(
            self,
            _criar_categoria_com_nome,
            nome,
            ao_sucesso=self._ao_criar_categoria_sucesso,
            ao_erro=self._ao_criar_categoria_erro,
        )

    def _ao_criar_categoria_sucesso(self, resultado):

        response, nome = resultado

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

    def _ao_criar_categoria_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def gerenciar_categorias(self):

        dialogo = GerenciarCategoriasDialog(parent=self)
        dialogo.exec()

        self._carregar_categorias()

    # ==========================================
    # MARCA
    # ==========================================

    def _carregar_marcas(self):

        # preserva a marca ja selecionada (mesmo motivo de
        # _carregar_categorias) -- guarda o ID, nao o texto, porque o
        # combo de marca nao e' editavel (item sempre tem itemData)
        self._marca_selecionada_pendente = self.marca.currentData()

        rodar_em_thread(
            self,
            listar_marcas,
            ao_sucesso=self._ao_carregar_marcas_sucesso,
        )

    def _ao_carregar_marcas_sucesso(self, marcas):

        self.marca.clear()
        self.marca.addItem("Sem marca", None)

        for m in marcas:
            if m.get("ativo", True):
                self.marca.addItem(m["nome"], m["id"])

        indice = self.marca.findData(self._marca_selecionada_pendente)
        self.marca.setCurrentIndex(indice if indice >= 0 else 0)

    def criar_nova_marca(self):

        nome, ok = QInputDialog.getText(
            self,
            "Nova Marca",
            "Nome da nova marca:"
        )

        if not ok or not nome.strip():
            return

        nome = nome.strip()

        rodar_em_thread(
            self,
            _criar_marca_com_nome,
            nome,
            ao_sucesso=self._ao_criar_marca_sucesso,
            ao_erro=self._ao_criar_marca_erro,
        )

    def _ao_criar_marca_sucesso(self, resultado):

        response, nome = resultado

        if response.status_code in (200, 201):

            marca_id = response.json()["id"]

            if self.marca.findData(marca_id) < 0:
                self.marca.addItem(nome, marca_id)

            self.marca.setCurrentIndex(self.marca.findData(marca_id))

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_criar_marca_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def gerenciar_marcas(self):

        dialogo = GerenciarMarcasDialog(parent=self)
        dialogo.exec()

        self._carregar_marcas()

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
    # KIT / COMBO
    # ==========================================

    def _alternar_kit(self, marcado):
        habilitado = marcado and self.produto is not None
        self.bt_adicionar_componente.setEnabled(habilitado)
        self.bt_remover_componente.setEnabled(habilitado)

    def _carregar_itens_kit(self):
        rodar_em_thread(
            self,
            listar_itens_kit,
            self.produto["id"],
            ao_sucesso=self._ao_carregar_itens_kit_sucesso,
            ao_erro=self._ao_carregar_itens_kit_erro,
        )

    def _ao_carregar_itens_kit_sucesso(self, itens):
        self.kit_itens = itens

        self.tabela_kit.setRowCount(len(itens))

        for linha, item in enumerate(itens):
            self.tabela_kit.setItem(
                linha, 0,
                QTableWidgetItem(item.get("produto_componente_nome") or ""),
            )
            self.tabela_kit.setItem(
                linha, 1, QTableWidgetItem(str(item["quantidade"]))
            )

    def _ao_carregar_itens_kit_erro(self, erro):
        QMessageBox.critical(
            self, "Erro",
            f"Não foi possível carregar os componentes do kit.\n{erro}"
        )

    def adicionar_componente_kit(self):

        if not self.produto:
            return

        rodar_em_thread(
            self,
            listar_produtos,
            ao_sucesso=self._ao_listar_produtos_para_kit,
            ao_erro=self._ao_carregar_itens_kit_erro,
        )

    def _ao_listar_produtos_para_kit(self, produtos):

        candidatos = [
            p for p in produtos
            if p["id"] != self.produto["id"] and not p.get("eh_kit")
        ]

        tela = PesquisaWindow(
            titulo="Adicionar componente do kit",
            colunas=["Código", "Nome", "Estoque"],
            campos=["codigo", "nome", "estoque"],
            dados=candidatos,
            chave_pesquisa="nome",
        )

        if tela.exec() != QDialog.Accepted:
            return

        quantidade, ok = QInputDialog.getInt(
            self, "Quantidade",
            f"Quantos \"{tela.selecionado['nome']}\" entram em 1 unidade "
            "do kit?",
            1, 1, 999999,
        )

        if not ok:
            return

        rodar_em_thread(
            self,
            adicionar_item_kit,
            self.produto["id"],
            tela.selecionado["id"],
            quantidade,
            ao_sucesso=self._ao_mutar_kit_sucesso,
            ao_erro=self._ao_carregar_itens_kit_erro,
        )

    def remover_componente_kit(self):

        linha = self.tabela_kit.currentRow()

        if linha < 0:
            QMessageBox.warning(self, "Aviso", "Selecione um componente.")
            return

        item = self.kit_itens[linha]

        rodar_em_thread(
            self,
            remover_item_kit,
            self.produto["id"],
            item["id"],
            ao_sucesso=self._ao_mutar_kit_sucesso,
            ao_erro=self._ao_carregar_itens_kit_erro,
        )

    def _ao_mutar_kit_sucesso(self, response):
        if response.status_code in (200, 201):
            self._carregar_itens_kit()
        else:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    # ==========================================
    # VARIACOES (COR/TAMANHO)
    # ==========================================

    def _carregar_variacoes(self):
        rodar_em_thread(
            self,
            listar_variacoes,
            self.produto["id"],
            ao_sucesso=self._ao_carregar_variacoes_sucesso,
            ao_erro=self._ao_carregar_variacoes_erro,
        )

    def _ao_carregar_variacoes_sucesso(self, variacoes):
        self.tabela_variacoes.setRowCount(len(variacoes))

        for linha, v in enumerate(variacoes):
            self.tabela_variacoes.setItem(
                linha, 0, QTableWidgetItem(v.get("nome") or "")
            )
            self.tabela_variacoes.setItem(
                linha, 1, QTableWidgetItem(v.get("cor") or "")
            )
            self.tabela_variacoes.setItem(
                linha, 2, QTableWidgetItem(v.get("tamanho") or "")
            )
            self.tabela_variacoes.setItem(
                linha, 3, QTableWidgetItem(str(v.get("estoque", 0)))
            )

    def _ao_carregar_variacoes_erro(self, erro):
        QMessageBox.critical(
            self, "Erro",
            f"Não foi possível carregar as variações.\n{erro}"
        )

    def nova_variacao(self):

        if not self.produto:
            return

        tela = CadastroProdutoWindow(produto_pai=self.produto)

        if tela.exec() != QDialog.Accepted:
            return

        self._nova_variacao_tela = tela

        rodar_em_thread(
            self,
            cadastrar_produto,
            tela.dados,
            ao_sucesso=self._ao_nova_variacao_sucesso,
            ao_erro=self._ao_carregar_variacoes_erro,
        )

    def _ao_nova_variacao_sucesso(self, response):
        if response.status_code == 201:
            self._carregar_variacoes()
        else:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

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

        rodar_em_thread(
            self,
            _buscar_produto_externo_com_flag,
            codigo,
            silencioso,
            ao_sucesso=self._ao_buscar_automatico_sucesso,
            ao_erro=self._ao_buscar_automatico_erro,
            ao_finalizar=self._ao_buscar_automatico_finalizado,
        )

    def _ao_buscar_automatico_sucesso(self, resultado_com_flag):

        resultado, silencioso = resultado_com_flag

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

    def _ao_buscar_automatico_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível buscar o produto.\n{erro}"
        )

    def _ao_buscar_automatico_finalizado(self):
        self.bt_buscar.setEnabled(True)

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
    # GALERIA DE FOTOS (edição apenas)
    # ==========================================

    def _carregar_galeria_fotos(self):
        rodar_em_thread(
            self,
            listar_fotos_produto,
            self.produto["id"],
            ao_sucesso=self._ao_carregar_galeria_sucesso,
        )

    def _ao_carregar_galeria_sucesso(self, fotos):

        # remove todas as miniaturas antigas, mantendo so' o botao "+"
        # (sempre o primeiro item do layout)
        while self.linha_galeria.count() > 2:
            item = self.linha_galeria.takeAt(1)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for foto in fotos:
            rodar_em_thread(
                self,
                _buscar_miniatura_com_info,
                self.produto["id"],
                foto,
                ao_sucesso=self._ao_carregar_miniatura_sucesso,
            )

    def _ao_carregar_miniatura_sucesso(self, resultado):

        foto, imagem_bytes = resultado

        if not imagem_bytes:
            return

        miniatura = self._construir_miniatura_foto(foto, imagem_bytes)
        # insere antes do addStretch() (ultimo item do layout)
        self.linha_galeria.insertWidget(
            self.linha_galeria.count() - 1, miniatura
        )

    def _construir_miniatura_foto(self, foto, imagem_bytes):

        quadro = QFrame()
        quadro.setFixedSize(56, 76)
        quadro.setStyleSheet("background:transparent; border:none;")

        col = QVBoxLayout(quadro)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        lbl_img = QLabel()
        lbl_img.setFixedSize(56, 56)
        lbl_img.setAlignment(Qt.AlignCenter)
        borda = tokens.PRIMARIA if foto.get("principal") else tokens.BORDA
        lbl_img.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
            border:2px solid {borda};
        """)

        pixmap = QPixmap()
        pixmap.loadFromData(imagem_bytes)
        if not pixmap.isNull():
            lbl_img.setPixmap(
                pixmap.scaled(
                    52, 52, Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
            )

        linha_acoes = QHBoxLayout()
        linha_acoes.setSpacing(2)
        linha_acoes.setContentsMargins(0, 0, 0, 0)

        bt_principal = QPushButton()
        bt_principal.setFixedSize(20, 18)
        bt_principal.setCursor(Qt.PointingHandCursor)
        bt_principal.setToolTip(
            "Foto principal" if foto.get("principal")
            else "Tornar principal"
        )
        bt_principal.setAccessibleName(bt_principal.toolTip())
        bt_principal.setIcon(
            icone(
                "star-filled" if foto.get("principal") else "star",
                cor=tokens.ALERTA if foto.get("principal") else tokens.TEXTO_TERCIARIO,
                tamanho=12,
            )
        )
        bt_principal.setEnabled(not foto.get("principal"))
        bt_principal.setStyleSheet(
            "background:transparent; border:none;"
        )
        bt_principal.clicked.connect(
            lambda: self._tornar_foto_principal(foto["id"])
        )

        bt_excluir = QPushButton()
        bt_excluir.setFixedSize(20, 18)
        bt_excluir.setCursor(Qt.PointingHandCursor)
        bt_excluir.setToolTip("Remover foto")
        bt_excluir.setAccessibleName("Remover foto")
        bt_excluir.setIcon(icone("trash-2", cor=tokens.ERRO, tamanho=12))
        bt_excluir.setStyleSheet("background:transparent; border:none;")
        bt_excluir.clicked.connect(
            lambda: self._remover_foto_extra(foto["id"])
        )

        linha_acoes.addWidget(bt_principal)
        linha_acoes.addWidget(bt_excluir)

        col.addWidget(lbl_img)
        col.addLayout(linha_acoes)

        return quadro

    def adicionar_foto_extra(self):

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
                self, "Imagem inválida", "Não foi possível abrir essa imagem."
            )
            return

        imagem_base64 = base64.b64encode(imagem_comprimida).decode("ascii")

        self.bt_adicionar_foto_extra.setEnabled(False)

        rodar_em_thread(
            self,
            adicionar_foto_produto,
            self.produto["id"],
            imagem_base64,
            False,
            ao_sucesso=self._ao_mutar_galeria_sucesso,
            ao_erro=self._ao_mutar_galeria_erro,
            ao_finalizar=self._ao_mutar_galeria_finalizado,
        )

    def _tornar_foto_principal(self, foto_id):
        rodar_em_thread(
            self,
            marcar_foto_principal,
            self.produto["id"],
            foto_id,
            ao_sucesso=self._ao_mutar_galeria_sucesso,
            ao_erro=self._ao_mutar_galeria_erro,
        )

    def _remover_foto_extra(self, foto_id):

        resposta = QMessageBox.question(
            self, "Remover foto", "Remover essa foto do produto?"
        )

        if resposta != QMessageBox.Yes:
            return

        rodar_em_thread(
            self,
            remover_foto_produto,
            self.produto["id"],
            foto_id,
            ao_sucesso=self._ao_mutar_galeria_sucesso,
            ao_erro=self._ao_mutar_galeria_erro,
        )

    def _ao_mutar_galeria_sucesso(self, response):

        if response.status_code in (200, 201):
            self._carregar_galeria_fotos()
            # a principal pode ter mudado (marcar/remover) -- recarrega
            # tambem a previa grande de cima, que le da mesma fonte
            rodar_em_thread(
                self,
                obter_foto_produto,
                self.produto["id"],
                ao_sucesso=self._ao_carregar_foto_sucesso,
            )
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutar_galeria_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutar_galeria_finalizado(self):
        self.bt_adicionar_foto_extra.setEnabled(True)

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
