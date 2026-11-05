"""Menu do topo (Vertex 2.0) -- substitui o menu lateral.

As 17 telas viram poucos grupos numa barra azul em cima (Vender,
Estoque, Pessoas, Financeiro...); clicar num grupo abre um painel com
as telas dele, cada uma com uma linha explicando pra que serve. Emite
item_clicado(chave), a mesma API que o menu lateral tinha."""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from design import tokens
from design.header import _BlocoClicavel, _Popover
from design.icons import icone
from utils.acessibilidade import movimento_reduzido

# (rotulo, icone, [chaves de ITENS_MENU]) -- grupo com 1 tela vira botao
# direto (sem painel). Toda tela do menu tem que estar aqui (ver
# tests/test_menu_topo.py), senao fica inalcancavel.
GRUPOS = [
    ("Início", "home", ["dashboard"]),
    ("Vender", "shopping-cart", ["pdv", "vendas", "caixa"]),
    ("Estoque", "package", ["produtos", "ajuste_estoque", "transferencia_estoque",
                            "contagem_estoque", "vitrine"]),
    ("Pessoas", "users", ["clientes", "fornecedores"]),
    ("Financeiro", "wallet", ["contas_pagar", "conciliacao_bancaria",
                              "visao_geral", "relatorios"]),
    ("Inteligência", "lightbulb", ["inteligencia"]),
    ("Ajustes", "settings", ["config"]),
]

DESCRICOES = {
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
    "contas_pagar": "Boletos e vencimentos",
    "conciliacao_bancaria": "Conferir Pix e cartão",
    "visao_geral": "Entrou, saiu e sobrou",
    "relatorios": "Vendas, caixa e estoque",
}


class _ItemPainel(_BlocoClicavel):

    def __init__(self, titulo, descricao, icone_nome):
        super().__init__()
        self.setObjectName("itemPainel")
        self.setAccessibleName(f"{titulo}: {descricao}")
        self.setStyleSheet(f"""
            QFrame#itemPainel {{ background: transparent; border: none;
                                 border-radius: {tokens.RADIUS_SM}px; }}
            QFrame#itemPainel:hover {{ background: {tokens.FUNDO}; }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        lbl_icone = QLabel()
        lbl_icone.setFixedSize(36, 36)
        lbl_icone.setAlignment(Qt.AlignCenter)
        lbl_icone.setPixmap(icone(icone_nome, cor=tokens.PRIMARIA, tamanho=18).pixmap(18, 18))
        lbl_icone.setStyleSheet(
            f"background: {tokens.PRIMARIA_CLARA}; border: none; border-radius: {tokens.RADIUS_SM}px;"
        )
        layout.addWidget(lbl_icone)

        textos = QVBoxLayout()
        textos.setSpacing(1)
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(
            f"background: transparent; border: none; color: {tokens.TEXTO}; "
            f"font-size: {tokens.TAMANHO_MD}px; font-weight: 600;"
        )
        lbl_desc = QLabel(descricao)
        lbl_desc.setStyleSheet(
            f"background: transparent; border: none; color: {tokens.TEXTO_SECUNDARIO}; "
            f"font-size: {tokens.TAMANHO_SM}px;"
        )
        textos.addWidget(lbl_titulo)
        textos.addWidget(lbl_desc)
        layout.addLayout(textos, stretch=1)


class _Painel(_Popover):
    """Painel suspenso de um grupo, com uma descida suave ao abrir
    (desligada pra quem pediu movimento reduzido no Windows)."""

    def __init__(self):
        super().__init__(largura=330)
        self.itens = {}
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)

    def abrir_sob(self, botao):
        ponto = botao.mapToGlobal(botao.rect().bottomLeft())
        self.move(ponto.x(), ponto.y() + 6)
        if movimento_reduzido():
            self.setWindowOpacity(1.0)
            self.show()
            return
        self.setWindowOpacity(0.0)
        self.show()
        self._anim.stop()
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()


class BarraMenu(QFrame):

    item_clicado = Signal(str)

    def __init__(self, nome_loja, itens_menu, pode_abrir, parent=None):
        """itens_menu/pode_abrir: ITENS_MENU e pode_abrir_tela de
        telas.principal (passados de fora pra evitar import circular)."""
        super().__init__(parent)

        self.setObjectName("barraMenu")
        self.setFixedHeight(60)
        self.setStyleSheet(f"QFrame#barraMenu {{ background: {tokens.SIDEBAR}; }}")

        info = {chave: (icone_nome, titulo) for chave, icone_nome, titulo in itens_menu}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(6)

        logo = QLabel("V")
        logo.setFixedSize(34, 34)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(f"""
            background: {tokens.PRIMARIA}; color: white;
            border-radius: {tokens.RADIUS_SM}px; font-size: 19px; font-weight: 800;
        """)
        layout.addWidget(logo)

        self.lbl_loja = QLabel(nome_loja)
        self.lbl_loja.setStyleSheet(
            f"background: transparent; color: white; font-size: {tokens.TAMANHO_MD}px; "
            "font-weight: 700; margin: 0 14px 0 4px;"
        )
        layout.addWidget(self.lbl_loja)

        self.botoes = {}      # rotulo do grupo -> botao
        self._grupo_de = {}   # chave da tela -> rotulo do grupo
        self.paineis = {}     # rotulo -> _Painel (so' grupos com 2+ telas)

        for rotulo, icone_nome, chaves in GRUPOS:
            visiveis = [c for c in chaves if c in info and pode_abrir(c)]
            if not visiveis:
                continue
            painel = None
            if len(visiveis) > 1:
                painel = _Painel()
                for chave in visiveis:
                    icone_tela, titulo = info[chave]
                    item = _ItemPainel(titulo, DESCRICOES.get(chave, ""), icone_tela)
                    item.clicked.connect(lambda c=chave, p=painel: (p.hide(), self.item_clicado.emit(c)))
                    painel.layout_corpo.addWidget(item)
                    painel.itens[chave] = item
                self.paineis[rotulo] = painel

            bt = QPushButton(f" {rotulo}  ▾" if painel else f" {rotulo}")
            bt.setCheckable(True)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setFixedHeight(40)
            bt.setIcon(icone(icone_nome, cor=tokens.TEXTO_SIDEBAR, tamanho=17))
            bt.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {tokens.TEXTO_SIDEBAR};
                    border: none; border-radius: {tokens.RADIUS_SM}px;
                    padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; font-weight: 600;
                }}
                QPushButton:hover {{ background: {tokens.SIDEBAR_HOVER}; color: white; }}
                QPushButton:checked {{ background: {tokens.SIDEBAR_ATIVO}; color: white; }}
            """)
            if painel:
                bt.clicked.connect(lambda _=False, b=bt, p=painel: self._abrir_painel(b, p))
            else:
                bt.clicked.connect(lambda _=False, c=visiveis[0]: self.item_clicado.emit(c))
            layout.addWidget(bt)
            self.botoes[rotulo] = bt
            for chave in visiveis:
                self._grupo_de[chave] = rotulo

        layout.addStretch()

        if "pdv" in self._grupo_de:
            self.bt_venda = QPushButton("  Nova venda   F3")
            self.bt_venda.setCursor(Qt.PointingHandCursor)
            self.bt_venda.setFixedHeight(42)
            self.bt_venda.setIcon(icone("plus", cor="white", tamanho=18))
            self.bt_venda.setStyleSheet(f"""
                QPushButton {{ background: {tokens.SUCESSO}; color: white; border: none;
                               border-radius: {tokens.RADIUS_SM}px; padding: 0 16px;
                               font-size: {tokens.TAMANHO_MD}px; font-weight: 700; }}
                QPushButton:hover {{ background: {tokens.SECUNDARIA_HOVER}; }}
            """)
            self.bt_venda.clicked.connect(lambda: self.item_clicado.emit("pdv"))
            layout.addWidget(self.bt_venda)

    def _abrir_painel(self, botao, painel):
        # o checked do botao reflete a tela atual, nao o clique
        botao.setChecked(self._grupo_de.get(self._atual) == self._rotulo(botao))
        painel.abrir_sob(botao)

    def _rotulo(self, botao):
        return next(r for r, b in self.botoes.items() if b is botao)

    _atual = None

    def definir_nome_loja(self, nome_loja):
        self.lbl_loja.setText(nome_loja)

    def selecionar(self, chave):
        self._atual = chave
        grupo = self._grupo_de.get(chave)
        for rotulo, bt in self.botoes.items():
            bt.setChecked(rotulo == grupo)
            cor = "white" if rotulo == grupo else tokens.TEXTO_SIDEBAR
            icone_nome = next(i for r, i, _ in GRUPOS if r == rotulo)
            bt.setIcon(icone(icone_nome, cor=cor, tamanho=17))
