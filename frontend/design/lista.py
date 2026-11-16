"""Peças compartilhadas das telas de lista (Produtos, Clientes, Boletos):

- FaixaAtencao: "Atenção hoje" -- 1 ou 2 avisos com botão de ação, some sozinha
  quando não há nada pra avisar.
- PainelDetalhe: ficha rápida à direita da tabela, aberta ao clicar numa linha.
- BarraProgresso: barra fina (estoque vs. mínimo, limite de crédito usado...).
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import (
    Avatar, Badge, BotaoPerigo, BotaoPrimario, BotaoSecundario, BotaoSucesso,
)

_BOTOES = {
    "primario": BotaoPrimario,
    "sucesso": BotaoSucesso,
    "secundario": BotaoSecundario,
    "perigo": BotaoPerigo,
}


def _limpar(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            _limpar(item.layout())


class BarraProgresso(QFrame):
    """Trilho fino com preenchimento proporcional (0 a 100)."""

    def __init__(self, percentual, cor, altura=6, parent=None):
        super().__init__(parent)
        self.setFixedHeight(altura)
        self.setStyleSheet(
            f"background:{tokens.BORDA}; border:none; border-radius:{altura // 2}px;"
        )
        self._pct = max(0.0, min(100.0, float(percentual)))
        self._preenchimento = QFrame(self)
        self._preenchimento.setStyleSheet(
            f"background:{cor}; border:none; border-radius:{altura // 2}px;"
        )

    def definir(self, percentual, cor=None):
        self._pct = max(0.0, min(100.0, float(percentual)))
        if cor:
            self._preenchimento.setStyleSheet(
                f"background:{cor}; border:none; border-radius:{self.height() // 2}px;"
            )
        self._ajustar()

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self._ajustar()

    def _ajustar(self):
        largura = int(self.width() * self._pct / 100)
        # um fio visivel mesmo com 1%: 0 de verdade fica sem preenchimento
        self._preenchimento.setGeometry(
            0, 0, max(self.height(), largura) if self._pct > 0 else 0, self.height()
        )


class FaixaAtencao(QFrame):
    """Faixa amarela "Atenção hoje". definir([(texto, rotulo_botao, callback)])
    -- lista vazia esconde a faixa; rotulo None mostra so' o texto."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("faixaAtencao")
        self.setStyleSheet(f"""
            QFrame#faixaAtencao {{
                background:{tokens.ALERTA_CLARO}; border:1px solid {tokens.ALERTA};
                border-radius:{tokens.RADIUS_MD}px;
            }}
        """)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(16, 8, 12, 8)
        self._layout.setSpacing(14)
        self.hide()

    def definir(self, avisos):
        _limpar(self._layout)

        if not avisos:
            self.hide()
            return

        sinal = QLabel()
        sinal.setPixmap(icone_pixmap("alert-triangle", cor=tokens.ALERTA_TEXTO, tamanho=20))
        sinal.setStyleSheet("background:transparent; border:none;")
        self._layout.addWidget(sinal)

        titulo = QLabel("Atenção hoje")
        titulo.setStyleSheet(
            f"background:transparent; border:none; color:{tokens.ALERTA_TEXTO}; "
            f"font-size:{tokens.TAMANHO_BASE}px; font-weight:700;"
        )
        self._layout.addWidget(titulo)

        for texto, rotulo, ao_clicar in avisos:
            divisor = QFrame()
            divisor.setFixedSize(1, 20)
            divisor.setStyleSheet(f"background:{tokens.ALERTA}; border:none;")
            self._layout.addWidget(divisor)

            lbl = QLabel(texto)
            lbl.setStyleSheet(
                f"background:transparent; border:none; color:{tokens.ALERTA_TEXTO}; "
                f"font-size:{tokens.TAMANHO_SM}px; font-weight:500;"
            )
            self._layout.addWidget(lbl)

            if rotulo is None:     # so' informa (ex.: quem nao pode fazer a acao)
                continue

            bt = QPushButton(rotulo)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setFixedHeight(28)
            bt.setStyleSheet(f"""
                QPushButton {{
                    background:transparent; color:{tokens.ALERTA_TEXTO};
                    border:1px solid {tokens.ALERTA}; border-radius:14px;
                    padding:0 12px; font-size:{tokens.TAMANHO_XS}px; font-weight:700;
                }}
                QPushButton:hover {{ background:{tokens.CARD}; }}
            """)
            bt.clicked.connect(lambda _=False, f=ao_clicar: f())
            self._layout.addWidget(bt)

        self._layout.addStretch()
        self.show()


class PainelDetalhe(QFrame):
    """Ficha rápida ao lado da tabela. Começa escondido; mostrar() preenche e
    abre, esconder() (ou o ×) fecha."""

    fechado = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("painelDetalhe")
        self.setFixedWidth(340)
        self.setStyleSheet(f"""
            QFrame#painelDetalhe {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_LG}px;
            }}
        """)
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(20, 14, 20, 18)
        self._v.setSpacing(8)
        self.hide()

    def esconder(self):
        self.hide()
        self.fechado.emit()

    def mostrar(self, nome, subtitulo, badge, campos, acoes, barra=None):
        """badge: (texto, variante) ou None. campos: [(rotulo, valor, variante)]
        com variante None/'erro'/'alerta'/'sucesso'. acoes: [(texto, estilo,
        icone, callback)]. barra: (rotulo, percentual, cor) ou None."""
        _limpar(self._v)

        topo = QHBoxLayout()
        topo.addStretch()
        fechar = QPushButton()
        fechar.setFixedSize(28, 28)
        fechar.setCursor(Qt.PointingHandCursor)
        fechar.setToolTip("Fechar ficha")
        fechar.setAccessibleName("Fechar ficha")
        fechar.setIcon(icone("x", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        fechar.setStyleSheet(
            f"QPushButton {{ background:transparent; border:none; border-radius:14px; }}"
            f"QPushButton:hover {{ background:{tokens.FUNDO}; }}"
        )
        fechar.clicked.connect(self.esconder)
        topo.addWidget(fechar)
        self._v.addLayout(topo)

        self._v.addWidget(Avatar(nome, 64), 0, Qt.AlignHCenter)

        lbl_nome = QLabel(nome)
        lbl_nome.setWordWrap(True)
        lbl_nome.setAlignment(Qt.AlignHCenter)
        lbl_nome.setStyleSheet(
            f"background:transparent; border:none; color:{tokens.TEXTO}; "
            f"font-size:{tokens.TAMANHO_LG}px; font-weight:700;"
        )
        self._v.addWidget(lbl_nome)

        if subtitulo:
            lbl_sub = QLabel(subtitulo)
            lbl_sub.setAlignment(Qt.AlignHCenter)
            lbl_sub.setStyleSheet(
                f"background:transparent; border:none; color:{tokens.TEXTO_TERCIARIO}; "
                f"font-size:{tokens.TAMANHO_SM}px;"
            )
            self._v.addWidget(lbl_sub)

        if badge:
            self._v.addWidget(Badge(badge[0], badge[1]), 0, Qt.AlignHCenter)

        self._v.addSpacing(6)

        cores = {
            "erro": tokens.ERRO, "alerta": tokens.ALERTA_TEXTO,
            "sucesso": tokens.SECUNDARIA_HOVER, None: tokens.TEXTO,
        }
        for rotulo, valor, variante in campos:
            linha = QFrame()
            linha.setObjectName("linhaCampo")
            linha.setStyleSheet(
                f"QFrame#linhaCampo {{ background:transparent; border:none; "
                f"border-top:1px solid {tokens.BORDA}; }}"
            )
            h = QHBoxLayout(linha)
            h.setContentsMargins(0, 8, 0, 8)
            esquerda = QLabel(rotulo)
            esquerda.setStyleSheet(
                f"background:transparent; border:none; color:{tokens.TEXTO_SECUNDARIO}; "
                f"font-size:{tokens.TAMANHO_SM}px;"
            )
            direita = QLabel(str(valor))
            direita.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            direita.setStyleSheet(
                f"background:transparent; border:none; color:{cores.get(variante, tokens.TEXTO)}; "
                f"font-size:{tokens.TAMANHO_BASE}px; font-weight:700;"
            )
            h.addWidget(esquerda)
            h.addStretch()
            h.addWidget(direita)
            self._v.addWidget(linha)

        if barra:
            rotulo, percentual, cor = barra
            self._v.addSpacing(4)
            legenda = QLabel(rotulo)
            legenda.setStyleSheet(
                f"background:transparent; border:none; color:{tokens.TEXTO_SECUNDARIO}; "
                f"font-size:{tokens.TAMANHO_XS}px;"
            )
            self._v.addWidget(legenda)
            self._v.addWidget(BarraProgresso(percentual, cor, altura=8))

        self._v.addSpacing(10)
        for texto, estilo, icone_nome, ao_clicar in acoes:
            bt = _BOTOES[estilo](texto, icone_nome=icone_nome)
            bt.setAutoDefault(False)
            bt.clicked.connect(lambda _=False, f=ao_clicar: f())
            self._v.addWidget(bt)

        self._v.addStretch()
        self.show()


def pagina_rolavel(layout_pai):
    """Tudo que for adicionado ao layout devolvido rola junto com a página
    (cards e filtros somem ao descer a lista); o que fica em `layout_pai`
    -- cabeçalho, rodapé -- continua fixo. Devolve (rolagem, layout)."""
    from PySide6.QtWidgets import QScrollArea

    rolagem = QScrollArea()
    rolagem.setWidgetResizable(True)
    rolagem.setFrameShape(QFrame.NoFrame)
    rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    rolagem.setStyleSheet(f"""
        QScrollArea {{ border:none; background:transparent; }}
        QScrollBar:vertical {{ background:transparent; width:10px; margin:0; }}
        QScrollBar::handle:vertical {{
            background:{tokens.BORDA_FORTE}; border-radius:5px; min-height:30px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:transparent; }}
    """)
    conteudo = QWidget()
    conteudo.setStyleSheet("background:transparent;")
    rolagem.setWidget(conteudo)
    layout_pai.addWidget(rolagem, stretch=1)
    layout = QVBoxLayout(conteudo)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(16)
    return rolagem, layout


class PainelFixo(QWidget):
    """Põe um painel lateral (ficha rápida, resumo) ao lado de uma lista
    que rola com a página, e o faz acompanhar a rolagem: o painel do item
    selecionado não some lá em cima quando a lista é longa."""

    def __init__(self, painel, rolagem, margem=8, altura_da_janela=False):
        super().__init__()
        self._painel, self._rolagem, self._margem = painel, rolagem, margem
        # painel com área que estica (ex.: extrato do cliente): ocupa a
        # altura visível da página, como ocupava quando a lista tinha rolagem própria
        self._altura_da_janela = altura_da_janela
        if altura_da_janela:
            rolagem.viewport().installEventFilter(self)
            self._ajustar_altura()
        self.setStyleSheet("background:transparent;")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.addWidget(painel, 0, Qt.AlignTop)
        self._lay.addStretch()
        rolagem.verticalScrollBar().valueChanged.connect(self._acompanhar)

    def eventFilter(self, obj, evento):
        from PySide6.QtCore import QEvent

        if evento.type() == QEvent.Resize:
            self._ajustar_altura()
        return super().eventFilter(obj, evento)

    def _ajustar_altura(self):
        self._painel.setFixedHeight(max(320, self._rolagem.viewport().height() - 2 * self._margem))

    def _acompanhar(self, valor):
        from PySide6.QtCore import QPoint

        topo = self.mapTo(self._rolagem.widget(), QPoint(0, 0)).y() - self._lay.contentsMargins().top()
        descida = max(0, valor - topo + self._margem)
        limite = max(0, self.height() - self._painel.height())
        self._lay.setContentsMargins(0, min(descida, limite), 0, 0)
