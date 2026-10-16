import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QStyledItemDelegate,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
)

from design import tokens
from design.icons import icone_pixmap


# ícone do sistema no lugar dos emojis antigos (que viravam quadrado em
# máquina sem fonte de emoji e destoavam do resto do sistema) --
# PainelSecao continua aceitando o emoji pra não quebrar quem chama
_ICONE_POR_EMOJI = {
    "\U0001f4c8": "trending-up", "\U0001f4e6": "package", "\U0001f4b3": "credit-card",
    "\U0001f53b": "filter", "\U0001f3ec": "store", "\U0001f504": "refresh-cw",
    "\U0001f4b0": "dollar-sign", "\U0001f4c5": "calendar", "\U0001f525": "bar-chart-2",
    "\U0001f6d2": "shopping-cart", "\U0001f3ed": "truck", "\u23f1\ufe0f": "calendar",
    "\U0001f40c": "alert-triangle", "\U0001f534": "alert-triangle", "\U0001f3af": "star",
    "\U0001f465": "users", "\U0001f550": "calendar",
}


_NUMERO = re.compile(r"^[\s+\-−–R$]*[\d.,]+\s*(%|x|un\.?|dias?)?$")


class _AlinhaNumeros(QStyledItemDelegate):
    """Valor (R$, %, quantidade) alinhado à direita, como em planilha --
    e o cabeçalho da coluna acompanha. Vale pra toda tabela que passa
    por _estilizar_tabela, sem mexer em cada lugar que preenche célula."""

    def __init__(self, tabela):
        super().__init__(tabela)
        self._tabela = tabela
        self._colunas_numericas = set()

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        texto = str(index.data() or "").strip()
        if texto and texto != "—" and _NUMERO.match(texto):
            option.displayAlignment = Qt.AlignRight | Qt.AlignVCenter
            coluna = index.column()
            if coluna not in self._colunas_numericas:
                self._colunas_numericas.add(coluna)
                cabecalho = self._tabela.horizontalHeaderItem(coluna)
                if cabecalho is not None:
                    cabecalho.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)


class LinhaBarra(QFrame):
    """Uma linha de 'Nome / valor' com uma barra de progresso simples,
    usada tanto no ranking de produtos quanto no mix de pagamentos.
    Mantém a mesma assinatura de sempre porque telas/visao_geral.py
    também importa e usa esta classe diretamente."""

    def __init__(self, titulo, subtitulo, valor_texto, percentual, cor):

        super().__init__()

        self.setStyleSheet("QFrame{background:transparent; border:none;}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        topo = QHBoxLayout()

        col_texto = QVBoxLayout()
        col_texto.setSpacing(0)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_BASE}px; font-weight:700; color:{tokens.TEXTO};
            background:transparent;
        """)

        col_texto.addWidget(lbl_titulo)

        if subtitulo:
            lbl_sub = QLabel(subtitulo)
            lbl_sub.setStyleSheet(f"""
                font-size:{tokens.TAMANHO_XS}px; color:{tokens.TEXTO_TERCIARIO};
                background:transparent;
            """)
            col_texto.addWidget(lbl_sub)

        topo.addLayout(col_texto)
        topo.addStretch()

        lbl_valor = QLabel(valor_texto)
        lbl_valor.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_BASE}px; font-weight:700; color:{cor};
            background:transparent;
        """)

        topo.addWidget(lbl_valor)

        layout.addLayout(topo)

        barra_fundo = QFrame()
        barra_fundo.setFixedHeight(6)
        barra_fundo.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:3px; border:none;
        """)

        barra_layout = QHBoxLayout(barra_fundo)
        barra_layout.setContentsMargins(0, 0, 0, 0)

        barra_preenchida = QFrame()
        barra_preenchida.setFixedHeight(6)
        barra_preenchida.setStyleSheet(
            f"background:{cor}; border-radius:3px; border:none;"
        )

        largura_relativa = max(0, min(100, round(percentual)))

        barra_layout.addWidget(barra_preenchida, largura_relativa)
        barra_layout.addStretch(max(1, 100 - largura_relativa))

        layout.addWidget(barra_fundo)


class PainelSecao(QFrame):
    """Card com cabeçalho (ícone emoji + título) e corpo substituível.
    Mantém a assinatura PainelSecao(icone, titulo) porque
    telas/visao_geral.py também importa e instancia esta classe
    diretamente com essa ordem de parâmetros."""

    def __init__(self, icone, titulo):

        super().__init__()

        self.setObjectName("painelSecao")
        self.setStyleSheet(f"""
            QFrame#painelSecao {{
                background:{tokens.CARD};
                border-radius:{tokens.RADIUS_LG}px;
                border:1px solid {tokens.BORDA};
            }}
        """)

        self.layout_externo = QVBoxLayout(self)
        self.layout_externo.setContentsMargins(20, 18, 20, 18)
        self.layout_externo.setSpacing(12)

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(10)

        nome_icone = _ICONE_POR_EMOJI.get(icone, icone if icone.isascii() else "bar-chart-2")
        lbl_icone = QLabel()
        lbl_icone.setFixedSize(30, 30)
        lbl_icone.setAlignment(Qt.AlignCenter)
        lbl_icone.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; border:none;
            border-radius:{tokens.RADIUS_SM}px;
        """)
        lbl_icone.setPixmap(icone_pixmap(nome_icone, cor=tokens.PRIMARIA, tamanho=16))

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_LG}px; font-weight:700; color:{tokens.TEXTO};
            background:transparent; border:none;
        """)

        cabecalho.addWidget(lbl_icone)
        cabecalho.addWidget(lbl_titulo)
        cabecalho.addStretch()

        self.layout_externo.addLayout(cabecalho)

        self.corpo = QVBoxLayout()
        self.corpo.setSpacing(14)

        self.layout_externo.addLayout(self.corpo)

    def limpar_corpo(self):
        while self.corpo.count():
            item = self.corpo.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def adicionar_vazio(self, texto):
        lbl = QLabel(texto)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"""
            color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_SM}px;
            background:transparent; border:none; padding:12px;
        """)
        self.corpo.addWidget(lbl)
