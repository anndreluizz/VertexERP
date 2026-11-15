"""Navegação do Vertex (redesign): faixa única no topo com as abas das telas
abertas e a tela inicial de módulos (grade de blocos).

- BarraAbas: uma aba por tela aberta; a tela em si continua sendo um widget
  único dentro da PilhaPaginas -- fechar a aba só tira ela da barra.
- TelaModulos: o "Início" -- um bloco por tela, agrupado como no menu antigo.
"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from design import tokens
from design.icons import icone

# (rotulo, [chaves de ITENS_MENU]) -- toda tela do menu tem que estar aqui
# (ou em SO_NA_BUSCA) -- ver tests/test_navegacao.py.
GRUPOS = [
    ("Painel", ["dashboard"]),
    ("Vender", ["pdv", "vendas", "caixa"]),
    ("Estoque", ["produtos", "vitrine"]),
    ("Pessoas", ["clientes", "fornecedores"]),
    ("Financeiro", ["contas_pagar", "visao_geral", "relatorios"]),
    ("Inteligência", ["inteligencia"]),
    ("Ajustes", ["config"]),
]

# telas sem bloco no Início (pouco usadas): continuam no ITENS_MENU e abrem
# pela busca Ctrl+K
SO_NA_BUSCA = {"ajuste_estoque", "transferencia_estoque", "contagem_estoque",
               "conciliacao_bancaria"}

DESCRICOES = {
    "dashboard": "Resumo do dia, gráficos e o que fazer hoje",
    "pdv": "Vender no balcão · F3",
    "vendas": "Histórico, troca, reimprimir",
    "caixa": "Abrir, sangria, fechar",
    "produtos": "Cadastro, preços e fotos",
    "ajuste_estoque": "Entrada, saída e perda",
    "transferencia_estoque": "Matriz e filial",
    "contagem_estoque": "Conferir o estoque físico",
    "vitrine": "O que aparece no site da loja",
    "clientes": "Fichas, fiado e cobrança",
    "fornecedores": "Contatos e compras",
    "contas_pagar": "Vencimentos e contas fixas",
    "conciliacao_bancaria": "Conferir Pix e cartão",
    "visao_geral": "Entrou, saiu e sobrou",
    "relatorios": "Vendas, caixa e estoque",
    "inteligencia": "O que vende, o que parou, o que repor",
    "config": "Loja, usuários, backup",
}

CHAVE_INICIO = "modulos"


def _sombra(widget):
    s = QGraphicsDropShadowEffect(widget)
    s.setBlurRadius(tokens.SOMBRA_CARD_BLUR)
    s.setOffset(0, tokens.SOMBRA_CARD_Y)
    cor = QColor(tokens.SOMBRA_COR)
    cor.setAlpha(tokens.SOMBRA_CARD_ALPHA)
    s.setColor(cor)
    widget.setGraphicsEffect(s)


# ==========================================
# ABAS DAS TELAS ABERTAS
# ==========================================

class _Aba(QFrame):

    clicada = Signal(str)
    fechada = Signal(str)

    def __init__(self, chave, titulo, icone_nome, fechavel):
        super().__init__()
        self.chave, self._icone, self._fechavel = chave, icone_nome, fechavel
        self.setObjectName("aba")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 6 if fechavel else 12, 0)
        layout.setSpacing(4)

        self.setMaximumWidth(190)
        self.setToolTip(titulo)
        self.bt = QPushButton()
        self.bt.setText(self.bt.fontMetrics().elidedText(f"  {titulo}", Qt.ElideRight, 130))
        self.bt.setCursor(Qt.PointingHandCursor)
        self.bt.setIconSize(QSize(16, 16))
        self.bt.clicked.connect(lambda: self.clicada.emit(chave))
        layout.addWidget(self.bt)

        if fechavel:
            x = QPushButton()
            x.setFixedSize(22, 22)
            x.setCursor(Qt.PointingHandCursor)
            x.setToolTip("Fechar aba (Ctrl+W)")
            x.setIcon(icone("x", cor=tokens.TEXTO_TERCIARIO, tamanho=14))
            x.setStyleSheet(
                f"QPushButton {{ border: none; border-radius: 11px; background: transparent; }}"
                f"QPushButton:hover {{ background: {tokens.BORDA}; }}"
            )
            x.clicked.connect(lambda: self.fechada.emit(chave))
            layout.addWidget(x)

        self.definir_ativa(False)

    def definir_ativa(self, ativa):
        cor = tokens.PRIMARIA if ativa else tokens.TEXTO_SECUNDARIO
        self.bt.setIcon(icone(self._icone, cor=cor, tamanho=16))
        self.bt.setStyleSheet(
            f"QPushButton {{ border: none; background: transparent; color: {cor}; "
            f"font-size: {tokens.TAMANHO_SM}px; font-weight: {700 if ativa else 500}; }}"
        )
        self.setStyleSheet(f"""
            QFrame#aba {{ background: {tokens.CARD if ativa else 'transparent'};
                          border: 1px solid {tokens.BORDA if ativa else 'transparent'};
                          border-bottom: none;
                          border-top-left-radius: {tokens.RADIUS_SM + 2}px;
                          border-top-right-radius: {tokens.RADIUS_SM + 2}px; }}
            QFrame#aba:hover {{ background: {tokens.CARD if ativa else tokens.PRIMARIA_CLARA}; }}
        """)


class BarraAbas(QFrame):
    """Única faixa do topo: abas das telas abertas à esquerda; Nova venda e
    o bloco do Header (olhinho, sino, perfil) à direita."""

    aba_clicada = Signal(str)
    aba_fechada = Signal(str)
    nova_venda = Signal()

    def __init__(self, pode_abrir=lambda chave: True, parent=None):
        super().__init__(parent)
        self.setObjectName("barraAbas")
        self.setFixedHeight(56)
        self.setStyleSheet(
            f"QFrame#barraAbas {{ background: {tokens.FUNDO}; "
            f"border-bottom: 1px solid {tokens.BORDA}; }}"
        )
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(20, 0, 16, 0)
        self._layout.setSpacing(10)

        # abas coladas na base da faixa (a aba ativa "abre" pra pagina embaixo);
        # com muitas abas a faixa rola na horizontal (roda do mouse) em vez de
        # empurrar o Nova venda e o perfil pra fora da tela
        self._rolagem = QScrollArea()
        self._rolagem.setWidgetResizable(True)
        self._rolagem.setFrameShape(QFrame.NoFrame)
        self._rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._rolagem.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._rolagem.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        miolo = QWidget()
        miolo.setStyleSheet("background: transparent;")
        coluna = QVBoxLayout(miolo)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.addStretch()
        self._abas_layout = QHBoxLayout()
        self._abas_layout.setSpacing(4)
        self._abas_layout.addStretch()
        coluna.addLayout(self._abas_layout)
        self._rolagem.setWidget(miolo)
        self._layout.addWidget(self._rolagem, stretch=1)

        if pode_abrir("pdv"):
            # no tema escuro o verde e' claro: texto branco nao tem contraste
            cor_texto = tokens.FUNDO if tokens.ESCURO_ATIVO else "white"
            self.bt_venda = QPushButton("  Nova venda  F3")
            self.bt_venda.setMinimumWidth(self.bt_venda.sizeHint().width() + 24)
            self.bt_venda.setCursor(Qt.PointingHandCursor)
            self.bt_venda.setFixedHeight(38)
            self.bt_venda.setIcon(icone("plus", cor=cor_texto, tamanho=18))
            self.bt_venda.setStyleSheet(f"""
                QPushButton {{ background: {tokens.SUCESSO}; color: {cor_texto}; border: none;
                               border-radius: {tokens.RADIUS_SM + 2}px; padding: 0 16px;
                               font-size: {tokens.TAMANHO_BASE}px; font-weight: 700; }}
                QPushButton:hover {{ background: {tokens.SECUNDARIA_HOVER}; }}
            """)
            self.bt_venda.clicked.connect(self.nova_venda)
            self._layout.addWidget(self.bt_venda)

        self._abas = {}   # chave -> _Aba, na ordem em que foram abertas
        self._atual = None

    def anexar(self, widget):
        """Bloco no fim da barra (o Header em modo na_barra)."""
        self._layout.addWidget(widget)

    @property
    def abertas(self):
        return list(self._abas)

    @property
    def atual(self):
        return self._atual

    def abrir(self, chave, titulo, icone_nome):
        if chave not in self._abas:
            aba = _Aba(chave, titulo, icone_nome, fechavel=chave != CHAVE_INICIO)
            aba.clicada.connect(self.aba_clicada)
            aba.fechada.connect(self.aba_fechada)
            self._abas_layout.insertWidget(self._abas_layout.count() - 1, aba)
            self._abas[chave] = aba
        self.selecionar(chave)

    def selecionar(self, chave):
        self._atual = chave
        for c, aba in self._abas.items():
            aba.definir_ativa(c == chave)
        if chave in self._abas:
            self._rolagem.ensureWidgetVisible(self._abas[chave])

    def fechar(self, chave):
        """Tira a aba e devolve a chave da vizinha que deve ficar na tela
        (a anterior; o início nunca fecha)."""
        if chave == CHAVE_INICIO or chave not in self._abas:
            return self._atual
        ordem = self.abertas
        vizinha = ordem[max(0, ordem.index(chave) - 1)]
        aba = self._abas.pop(chave)
        aba.hide()
        aba.setParent(None)
        aba.deleteLater()
        if self._atual == chave:
            self._atual = vizinha
        return vizinha


# ==========================================
# TELA INICIAL: GRADE DE MÓDULOS
# ==========================================

class _Bloco(QFrame):

    clicado = Signal(str)

    def __init__(self, chave, titulo, descricao, icone_nome):
        super().__init__()
        self.chave = chave
        self.setObjectName("bloco")
        self.setMinimumHeight(132)
        # largura vem so' das colunas da grade (blocos iguais, sem depender do texto)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setCursor(Qt.PointingHandCursor)
        self.setAccessibleName(f"{titulo}: {descricao}")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet(f"""
            QFrame#bloco {{ background: {tokens.CARD}; border: 1px solid {tokens.BORDA};
                            border-radius: {tokens.RADIUS_LG}px; }}
            QFrame#bloco:hover, QFrame#bloco:focus {{ border: 1.5px solid {tokens.PRIMARIA}; }}
        """)
        _sombra(self)

        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 16)
        v.setSpacing(2)

        ic = QLabel()
        ic.setFixedSize(44, 44)
        ic.setAlignment(Qt.AlignCenter)
        ic.setPixmap(icone(icone_nome, cor=tokens.PRIMARIA, tamanho=24).pixmap(24, 24))
        ic.setStyleSheet(
            f"background: {tokens.PRIMARIA_CLARA}; border: none; border-radius: {tokens.RADIUS_MD}px;"
        )
        v.addWidget(ic)
        v.addStretch()

        t = QLabel(titulo)
        t.setWordWrap(True)
        t.setStyleSheet(
            f"background: transparent; border: none; color: {tokens.TEXTO}; "
            f"font-size: {tokens.TAMANHO_LG}px; font-weight: 700;"
        )
        d = QLabel(descricao)
        d.setWordWrap(True)
        d.setStyleSheet(
            f"background: transparent; border: none; color: {tokens.TEXTO_SECUNDARIO}; "
            f"font-size: {tokens.TAMANHO_SM}px;"
        )
        v.addWidget(t)
        v.addWidget(d)
        for filho in (ic, t, d):
            filho.setAttribute(Qt.WA_TransparentForMouseEvents)

    def mousePressEvent(self, evento):
        if evento.button() == Qt.LeftButton:
            self.clicado.emit(self.chave)

    def keyPressEvent(self, evento):
        if evento.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicado.emit(self.chave)
        else:
            super().keyPressEvent(evento)


class TelaModulos(QScrollArea):

    escolhido = Signal(str)
    COLUNAS = 4

    def __init__(self, nome_usuario, itens_menu, pode_abrir, parent=None):
        """itens_menu/pode_abrir: ITENS_MENU e pode_abrir_tela de
        telas.principal (passados de fora pra evitar import circular)."""
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(f"""
            QScrollArea {{ background: {tokens.FUNDO}; border: none; }}
            QScrollBar:vertical {{ width: 10px; background: transparent; margin: 2px; }}
            QScrollBar::handle:vertical {{ background: {tokens.BORDA_FORTE}; border-radius: 4px; min-height: 40px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
        """)

        info = {chave: (icone_nome, titulo) for chave, icone_nome, titulo in itens_menu}
        self.blocos = {}

        corpo = QWidget()
        corpo.setObjectName("corpoModulos")
        corpo.setStyleSheet(f"QWidget#corpoModulos {{ background: {tokens.FUNDO}; }}")
        v = QVBoxLayout(corpo)
        v.setContentsMargins(36, 28, 36, 28)
        v.setSpacing(6)

        primeiro = nome_usuario.split()[0] if nome_usuario else ""
        saudacao = QLabel(f"Olá, {primeiro}" if primeiro else "Olá")
        saudacao.setStyleSheet(
            f"background: transparent; color: {tokens.TEXTO}; "
            f"font-size: {tokens.TAMANHO_XXL}px; font-weight: 700;"
        )
        pergunta = QLabel("O que você quer fazer agora?")
        pergunta.setStyleSheet(
            f"background: transparent; color: {tokens.TEXTO_SECUNDARIO}; "
            f"font-size: {tokens.TAMANHO_BASE}px;"
        )
        v.addWidget(saudacao)
        v.addWidget(pergunta)

        for rotulo, chaves in GRUPOS:
            visiveis = [c for c in chaves if c in info and pode_abrir(c)]
            if not visiveis:
                continue
            titulo = QLabel(rotulo.upper())
            titulo.setStyleSheet(
                f"background: transparent; color: {tokens.TEXTO_TERCIARIO}; "
                f"font-size: {tokens.TAMANHO_XS}px; font-weight: 700; letter-spacing: 1px;"
            )
            titulo.setContentsMargins(2, 18, 0, 4)
            v.addWidget(titulo)

            grade = QGridLayout()
            grade.setSpacing(16)
            for n, chave in enumerate(visiveis):
                icone_nome, nome = info[chave]
                bloco = _Bloco(chave, nome, DESCRICOES.get(chave, ""), icone_nome)
                bloco.clicado.connect(self.escolhido)
                grade.addWidget(bloco, n // self.COLUNAS, n % self.COLUNAS)
                self.blocos[chave] = bloco
            for c in range(self.COLUNAS):
                grade.setColumnStretch(c, 1)
            v.addLayout(grade)

        v.addStretch()
        self.setWidget(corpo)
