from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.responsive import tamanho_fixo_seguro
from design.widgets import Badge, Card
from utils.formatacao import formatar_moeda

_TAMANHO_FOTO = 130

_ROTULOS_UNIDADE = {"UN": "un.", "KG": "kg", "L": "L"}


class ProdutoCriadoDialog(QDialog):

    def __init__(self, produto, imagem_bytes=None, parent=None):

        super().__init__(parent)

        self.produto = produto
        self.editar_solicitado = False
        self.cadastrar_outro_solicitado = False

        self.setWindowTitle("Produto Criado")
        tamanho_fixo_seguro(self, 600, 800)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 20, 32, 26)
        layout.setSpacing(10)

        # ---- fechar ----

        linha_fechar = QHBoxLayout()
        linha_fechar.addStretch()

        bt_fechar = QPushButton()
        bt_fechar.setFixedSize(34, 34)
        bt_fechar.setCursor(Qt.PointingHandCursor)
        bt_fechar.setIcon(icone("x", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        bt_fechar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        bt_fechar.clicked.connect(self.reject)
        linha_fechar.addWidget(bt_fechar)

        layout.addLayout(linha_fechar)

        # ---- selo de sucesso (com halo) ----

        selo_wrapper = QFrame()
        selo_wrapper.setFixedSize(92, 92)
        selo_wrapper.setStyleSheet(f"""
            background:{tokens.SUCESSO_CLARO}; border-radius:46px;
        """)
        layout_selo = QVBoxLayout(selo_wrapper)
        layout_selo.setContentsMargins(0, 0, 0, 0)
        layout_selo.setAlignment(Qt.AlignCenter)

        selo = QLabel()
        selo.setFixedSize(62, 62)
        selo.setAlignment(Qt.AlignCenter)
        selo.setStyleSheet(f"""
            background:{tokens.SECUNDARIA}; border-radius:31px; border:none;
        """)
        selo.setPixmap(icone_pixmap("check", cor=tokens.TEXTO_CLARO, tamanho=26))
        layout_selo.addWidget(selo)

        layout.addWidget(selo_wrapper, alignment=Qt.AlignHCenter)
        layout.addSpacing(6)

        titulo = QLabel("Produto cadastrado com sucesso!")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setWordWrap(True)
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel("O item já está disponível no estoque.")
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(14)

        # ---- cartão com foto + dados + mini-estatísticas ----

        cartao = Card()
        cartao.setStyleSheet(f"""
            Card {{
                background:{tokens.FUNDO}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_MD}px;
            }}
        """)

        layout_cartao = QVBoxLayout(cartao)
        layout_cartao.setContentsMargins(18, 16, 18, 16)
        layout_cartao.setSpacing(14)

        linha_topo = QHBoxLayout()
        linha_topo.setSpacing(14)

        self.lbl_imagem = QLabel()
        self.lbl_imagem.setFixedSize(_TAMANHO_FOTO, _TAMANHO_FOTO)
        self.lbl_imagem.setAlignment(Qt.AlignCenter)
        self.lbl_imagem.setStyleSheet(f"""
            background:{tokens.CARD}; border-radius:{tokens.RADIUS_MD}px;
            border:1px solid {tokens.BORDA};
        """)
        self.lbl_imagem.setPixmap(
            icone_pixmap("package", cor=tokens.TEXTO_TERCIARIO, tamanho=40)
        )

        if imagem_bytes:
            pixmap = QPixmap()
            pixmap.loadFromData(imagem_bytes)
            self.lbl_imagem.setPixmap(
                pixmap.scaled(
                    _TAMANHO_FOTO, _TAMANHO_FOTO,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation,
                )
            )

        linha_topo.addWidget(self.lbl_imagem)

        col_dados = QVBoxLayout()
        col_dados.setSpacing(6)
        col_dados.setAlignment(Qt.AlignVCenter)

        lbl_nome = QLabel(produto.get("nome", ""))
        lbl_nome.setWordWrap(True)
        lbl_nome.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_LG}px; font-weight:800;
        """)
        col_dados.addWidget(lbl_nome)

        codigo_barras = produto.get("codigo_barras") or "—"
        lbl_codigo = QLabel(f"Código de barras: {codigo_barras}")
        lbl_codigo.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        col_dados.addWidget(lbl_codigo)

        linha_categoria = QHBoxLayout()
        linha_categoria.setSpacing(8)

        lbl_categoria_rotulo = QLabel("Categoria:")
        lbl_categoria_rotulo.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        linha_categoria.addWidget(lbl_categoria_rotulo)
        linha_categoria.addWidget(
            Badge(produto.get("categoria") or "Sem categoria", "info")
        )
        linha_categoria.addStretch()
        col_dados.addLayout(linha_categoria)

        linha_topo.addLayout(col_dados, 1)

        layout_cartao.addLayout(linha_topo)

        separador = QFrame()
        separador.setFixedHeight(1)
        separador.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        layout_cartao.addWidget(separador)

        linha_stats = QHBoxLayout()
        linha_stats.setSpacing(18)

        unidade_rotulo = _ROTULOS_UNIDADE.get(produto.get("unidade"), "un.")

        lbl_estoque = QLabel(f"{produto.get('estoque', 0)} {unidade_rotulo}")
        lbl_estoque.setStyleSheet(self._estilo_valor_estatistica())
        linha_stats.addLayout(self._mini_estatistica(
            "package", tokens.PRIMARIA, "Estoque", lbl_estoque,
        ))

        lbl_preco = QLabel(formatar_moeda(produto.get("preco_venda", 0)))
        lbl_preco.setStyleSheet(self._estilo_valor_estatistica())
        linha_stats.addLayout(self._mini_estatistica(
            "dollar-sign", tokens.SECUNDARIA, "Preço de venda", lbl_preco,
        ))

        ativo = produto.get("ativo", True)
        badge_status = Badge("Ativo" if ativo else "Inativo", "sucesso" if ativo else "neutro")
        linha_stats.addLayout(self._mini_estatistica(
            "shopping-cart", tokens.PRIMARIA, "Status", badge_status,
        ))

        layout_cartao.addLayout(linha_stats)

        layout.addWidget(cartao)

        # ---- banner informativo ----

        banner_frame = QFrame()
        banner_frame.setStyleSheet(f"""
            background:{tokens.SUCESSO_CLARO}; border-radius:{tokens.RADIUS_SM}px;
        """)
        banner_layout = QHBoxLayout(banner_frame)
        banner_layout.setContentsMargins(14, 10, 14, 10)
        banner_layout.setSpacing(8)

        icone_banner = QLabel()
        icone_banner.setFixedSize(18, 18)
        icone_banner.setStyleSheet("background:transparent; border:none;")
        icone_banner.setPixmap(icone_pixmap("check", cor=tokens.SECUNDARIA_HOVER, tamanho=13))
        banner_layout.addWidget(icone_banner)

        lbl_banner = QLabel("Agora este produto pode ser vendido no sistema.")
        lbl_banner.setWordWrap(True)
        lbl_banner.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.SECUNDARIA_HOVER};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        banner_layout.addWidget(lbl_banner, 1)

        layout.addWidget(banner_frame)
        layout.addSpacing(4)

        # ---- ações ----

        linha_botoes = QHBoxLayout()
        linha_botoes.setSpacing(10)

        bt_concluir = QPushButton("Concluir")
        bt_concluir.setCursor(Qt.PointingHandCursor)
        bt_concluir.setMinimumHeight(48)
        bt_concluir.setIcon(icone("check", cor="white", tamanho=16))
        bt_concluir.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.SECUNDARIA}; color:{tokens.TEXTO_CLARO};
                font-weight:700; border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.SECUNDARIA_HOVER}; }}
        """)
        bt_concluir.clicked.connect(self.accept)

        bt_editar = QPushButton("Editar produto")
        bt_editar.setCursor(Qt.PointingHandCursor)
        bt_editar.setMinimumHeight(48)
        bt_editar.setIcon(icone("edit-2", cor=tokens.TEXTO, tamanho=15))
        bt_editar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; color:{tokens.TEXTO};
                border:1.5px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                font-weight:700;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        bt_editar.clicked.connect(self.editar)

        linha_botoes.addWidget(bt_concluir)
        linha_botoes.addWidget(bt_editar)

        layout.addLayout(linha_botoes)

        separador2 = QFrame()
        separador2.setFixedHeight(1)
        separador2.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        layout.addWidget(separador2)

        bt_outro = QPushButton("Cadastrar outro produto")
        bt_outro.setCursor(Qt.PointingHandCursor)
        bt_outro.setMinimumHeight(44)
        bt_outro.setIcon(icone("plus", cor=tokens.PRIMARIA, tamanho=15))
        bt_outro.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA};
                border-radius:{tokens.RADIUS_SM}px; font-weight:700;
            }}
            QPushButton:hover {{ background:{tokens.BORDA}; }}
        """)
        bt_outro.clicked.connect(self.cadastrar_outro)
        layout.addWidget(bt_outro)

    # ==========================================

    def _estilo_valor_estatistica(self):
        return f"""
            background:transparent; border:none; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:800;
        """

    def _mini_estatistica(self, icone_nome, cor, rotulo, widget_valor):

        coluna = QVBoxLayout()
        coluna.setSpacing(4)

        icone_lbl = QLabel()
        icone_lbl.setFixedSize(28, 28)
        icone_lbl.setAlignment(Qt.AlignCenter)
        cor_rgb = QColor(cor)
        icone_lbl.setStyleSheet(f"""
            background: rgba({cor_rgb.red()}, {cor_rgb.green()}, {cor_rgb.blue()}, 0.12);
            border-radius:{tokens.RADIUS_SM}px; border:none;
        """)
        icone_lbl.setPixmap(icone_pixmap(icone_nome, cor=cor, tamanho=14))

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; border:none; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        coluna.addWidget(icone_lbl, 0, Qt.AlignLeft)
        coluna.addWidget(lbl_rotulo, 0, Qt.AlignLeft)
        coluna.addWidget(widget_valor, 0, Qt.AlignLeft)

        return coluna

    def editar(self):
        self.editar_solicitado = True
        self.accept()

    def cadastrar_outro(self):
        self.cadastrar_outro_solicitado = True
        self.accept()
