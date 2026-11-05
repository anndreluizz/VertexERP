"""Tela "Início" do Vertex 2.0: todos os módulos em cartões agrupados
(substitui o menu lateral). Cada cartão abre a tela numa aba."""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from design.icons import icone
from design.widgets import FlowLayout

# (titulo do grupo, [chaves de ITENS_MENU]) -- toda tela do menu tem que
# estar aqui (ver tests/test_vertex2_abas.py), senao fica inalcancavel.
GRUPOS = [
    ("Vender", ["pdv", "dashboard", "vendas", "caixa"]),
    ("Estoque", ["produtos", "ajuste_estoque", "transferencia_estoque",
                 "contagem_estoque", "vitrine"]),
    ("Pessoas", ["clientes", "fornecedores"]),
    ("Financeiro e gestão", ["contas_pagar", "conciliacao_bancaria",
                             "visao_geral", "relatorios", "inteligencia",
                             "config"]),
]

DESCRICOES = {
    "dashboard": "Vendas e caixa de hoje",
    "pdv": "Vender no balcão · F3",
    "vendas": "Histórico, troca, reimprimir",
    "caixa": "Abrir, sangria, fechar",
    "produtos": "Cadastro, preços e fotos",
    "ajuste_estoque": "Entrada, saída e perda",
    "transferencia_estoque": "Matriz e filial",
    "contagem_estoque": "Conferir o estoque físico",
    "vitrine": "O que aparece no site",
    "clientes": "Fichas, fiado e cobrança",
    "fornecedores": "Contatos e compras",
    "contas_pagar": "Boletos e vencimentos",
    "conciliacao_bancaria": "Conferir Pix e cartão",
    "visao_geral": "Entrou, saiu e sobrou",
    "relatorios": "Vendas, caixa e estoque",
    "inteligencia": "Quem cobrar, clientes sumidos",
    "config": "Loja, usuários, impressora",
}

DESTAQUE = "pdv"


class CartaoModulo(QPushButton):

    def __init__(self, titulo, descricao, icone_nome, destaque=False, parent=None):
        super().__init__(parent)

        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(QSize(292, 78))
        self.setAccessibleName(f"{titulo}: {descricao}")
        borda = f"2px solid {tokens.SUCESSO}" if destaque else f"1px solid {tokens.BORDA}"
        self.setStyleSheet(f"""
            CartaoModulo {{
                background: {tokens.CARD};
                border: {borda};
                border-radius: {tokens.RADIUS_LG}px;
                text-align: left;
            }}
            CartaoModulo:hover {{ border-color: {tokens.PRIMARIA}; }}
            CartaoModulo:focus {{ border: 2px solid {tokens.PRIMARIA}; }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 12, 10)
        layout.setSpacing(12)

        fundo = tokens.SUCESSO if destaque else tokens.PRIMARIA_CLARA
        cor = "white" if destaque else tokens.PRIMARIA
        lbl_icone = QLabel()
        lbl_icone.setFixedSize(44, 44)
        lbl_icone.setAlignment(Qt.AlignCenter)
        lbl_icone.setPixmap(icone(icone_nome, cor=cor, tamanho=22).pixmap(22, 22))
        lbl_icone.setStyleSheet(
            f"background: {fundo}; border-radius: {tokens.RADIUS_MD}px; border: none;"
        )
        layout.addWidget(lbl_icone)

        textos = QVBoxLayout()
        textos.setSpacing(2)
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(
            f"background: transparent; border: none; color: {tokens.TEXTO}; "
            f"font-size: {tokens.TAMANHO_LG}px; font-weight: 700;"
        )
        lbl_desc = QLabel(descricao)
        lbl_desc.setStyleSheet(
            f"background: transparent; border: none; color: {tokens.TEXTO_SECUNDARIO}; "
            f"font-size: {tokens.TAMANHO_SM}px;"
        )
        textos.addWidget(lbl_titulo)
        textos.addWidget(lbl_desc)
        layout.addLayout(textos, stretch=1)

        # o clique tem que chegar no botao, nao nos rotulos por cima
        for filho in (lbl_icone, lbl_titulo, lbl_desc):
            filho.setAttribute(Qt.WA_TransparentForMouseEvents)


class TelaModulos(QWidget):

    abrir = Signal(str)

    def __init__(self, itens_menu, pode_abrir, parent=None):
        """itens_menu: ITENS_MENU de telas.principal; pode_abrir:
        pode_abrir_tela (passados de fora pra nao importar a principal
        aqui e criar import circular)."""
        super().__init__(parent)

        self.setStyleSheet(f"background: {tokens.FUNDO};")
        info = {chave: (icone_nome, titulo) for chave, icone_nome, titulo in itens_menu}

        rolagem = QScrollArea(self)
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)
        externo.addWidget(rolagem)

        conteudo = QWidget()
        rolagem.setWidget(conteudo)
        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(32, 28, 32, 32)
        layout.setSpacing(10)

        titulo = QLabel("O que vamos fazer agora?")
        titulo.setStyleSheet(
            f"color: {tokens.TEXTO}; font-size: {tokens.TAMANHO_XXL}px; font-weight: 800;"
        )
        layout.addWidget(titulo)
        sub = QLabel(
            "Cada tela abre numa aba lá em cima. Dá para deixar o PDV aberto "
            "e consultar um cliente ao mesmo tempo.  Ctrl+W fecha a aba, "
            "Ctrl+Tab troca."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {tokens.TEXTO_SECUNDARIO}; font-size: {tokens.TAMANHO_MD}px;")
        layout.addWidget(sub)

        self.cartoes = {}
        for nome_grupo, chaves in GRUPOS:
            visiveis = [c for c in chaves if c in info and pode_abrir(c)]
            if not visiveis:
                continue
            lbl_grupo = QLabel(nome_grupo.upper())
            lbl_grupo.setStyleSheet(
                f"color: {tokens.TEXTO_SECUNDARIO}; font-size: {tokens.TAMANHO_SM}px; "
                "font-weight: 700; letter-spacing: 1px; margin-top: 18px;"
            )
            layout.addWidget(lbl_grupo)

            caixa = QWidget()
            fluxo = FlowLayout(caixa, espaco_h=12, espaco_v=12)
            for chave in visiveis:
                icone_nome, titulo_tela = info[chave]
                cartao = CartaoModulo(
                    titulo_tela, DESCRICOES.get(chave, ""), icone_nome,
                    destaque=(chave == DESTAQUE),
                )
                cartao.clicked.connect(lambda _=False, c=chave: self.abrir.emit(c))
                fluxo.addWidget(cartao)
                self.cartoes[chave] = cartao
            layout.addWidget(caixa)

        layout.addStretch()
