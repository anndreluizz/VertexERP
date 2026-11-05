"""Barra de abas do topo (Vertex 2.0) -- substitui o menu lateral.

Cada tela aberta vira uma aba, como no navegador: da' pra deixar o PDV
aberto e consultar um cliente sem perder a venda (as telas sao as
mesmas instancias de sempre na PilhaPaginas; fechar a aba so' esconde,
nao destroi nada). A aba "Início" e' fixa (sem X)."""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QTabBar

from design import tokens
from design.icons import icone

ABA_FIXA = "inicio"


class BarraAbas(QFrame):

    aba_selecionada = Signal(str)

    def __init__(self, nome_loja, parent=None):
        super().__init__(parent)

        self.setObjectName("barraAbas")
        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            QFrame#barraAbas {{ background: {tokens.SIDEBAR}; }}
            QTabBar {{ background: transparent; }}
            QTabBar::tab {{
                background: {tokens.SIDEBAR_HOVER};
                color: {tokens.TEXTO_SIDEBAR};
                border: none;
                border-top-left-radius: {tokens.RADIUS_SM}px;
                border-top-right-radius: {tokens.RADIUS_SM}px;
                padding: 0 10px 0 12px;
                margin-right: 4px;
                height: 38px;
                min-width: 90px;
                font-size: {tokens.TAMANHO_MD}px;
                font-weight: 600;
            }}
            QTabBar::tab:hover {{ background: {tokens.SIDEBAR_ATIVO}; color: white; }}
            QTabBar::tab:selected {{ background: {tokens.FUNDO}; color: {tokens.TEXTO}; }}
            QTabBar::scroller {{ width: 28px; }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(10)

        logo = QLabel("V")
        logo.setFixedSize(32, 32)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(f"""
            background: {tokens.PRIMARIA}; color: white;
            border-radius: {tokens.RADIUS_SM}px;
            font-size: 18px; font-weight: 800;
        """)
        layout.addWidget(logo, alignment=Qt.AlignVCenter)

        self.lbl_loja = QLabel(nome_loja)
        self.lbl_loja.setStyleSheet(
            f"background: transparent; color: white; "
            f"font-size: {tokens.TAMANHO_MD}px; font-weight: 700;"
        )
        layout.addWidget(self.lbl_loja, alignment=Qt.AlignVCenter)
        layout.addSpacing(8)

        self.barra = QTabBar()
        self.barra.setDocumentMode(True)
        self.barra.setDrawBase(False)
        self.barra.setExpanding(False)
        self.barra.setMovable(True)
        self.barra.setTabsClosable(True)
        self.barra.setUsesScrollButtons(True)
        self.barra.setElideMode(Qt.ElideRight)
        self.barra.setIconSize(QSize(16, 16))
        self.barra.currentChanged.connect(self._ao_mudar)
        self.barra.tabCloseRequested.connect(self.fechar_indice)
        layout.addWidget(self.barra, stretch=1, alignment=Qt.AlignBottom)

        self._icones = {}

    def definir_nome_loja(self, nome_loja):
        self.lbl_loja.setText(nome_loja)

    def chaves(self):
        return [self.barra.tabData(i) for i in range(self.barra.count())]

    def chave_atual(self):
        i = self.barra.currentIndex()
        return self.barra.tabData(i) if i >= 0 else None

    def abrir(self, chave, titulo, icone_nome=None):
        """Seleciona a aba da tela (criando se ainda nao existe) SEM
        emitir aba_selecionada -- quem chama ja' esta' exibindo a tela."""
        self.barra.blockSignals(True)
        try:
            chaves = self.chaves()
            if chave in chaves:
                indice = chaves.index(chave)
            else:
                indice = self.barra.addTab(titulo)
                self.barra.setTabData(indice, chave)
                self.barra.setTabToolTip(indice, titulo)
                if icone_nome:
                    self._icones[chave] = icone_nome
                self._pintar_icone(indice, selecionada=False)
                self.barra.setTabButton(
                    indice, QTabBar.RightSide,
                    None if chave == ABA_FIXA else self._botao_fechar(chave),
                )
            anterior = self.barra.currentIndex()
            self.barra.setCurrentIndex(indice)
            if anterior >= 0 and anterior != indice:
                self._pintar_icone(anterior, selecionada=False)
            self._pintar_icone(indice, selecionada=True)
        finally:
            self.barra.blockSignals(False)

    def _botao_fechar(self, chave):
        bt = QPushButton()
        bt.setFixedSize(22, 22)
        bt.setCursor(Qt.PointingHandCursor)
        bt.setToolTip("Fechar (Ctrl+W)")
        bt.setAccessibleName("Fechar aba")
        bt.setIcon(icone("x", cor=tokens.TEXTO_SIDEBAR_APAGADO, tamanho=14))
        bt.setStyleSheet(
            f"QPushButton {{ background: transparent; border: none; border-radius: 5px; }}"
            f"QPushButton:hover {{ background: {tokens.ERRO_CLARO}; }}"
        )
        # o indice muda quando outras abas fecham/movem: procura na hora
        bt.clicked.connect(lambda: self.fechar_indice(self.chaves().index(chave)))
        return bt

    def fechar_indice(self, indice):
        if self.barra.tabData(indice) == ABA_FIXA:
            return
        # removeTab seleciona a vizinha sozinho e emite currentChanged,
        # que exibe essa tela (ver _ao_mudar)
        self.barra.removeTab(indice)

    def fechar_atual(self):
        self.fechar_indice(self.barra.currentIndex())

    def proxima(self, passo=1):
        total = self.barra.count()
        if total:
            self.barra.setCurrentIndex((self.barra.currentIndex() + passo) % total)

    def _pintar_icone(self, indice, selecionada):
        nome = self._icones.get(self.barra.tabData(indice))
        if nome:
            cor = tokens.TEXTO if selecionada else tokens.TEXTO_SIDEBAR
            self.barra.setTabIcon(indice, icone(nome, cor=cor, tamanho=16))

    def _ao_mudar(self, indice):
        if indice < 0:
            return
        for i in range(self.barra.count()):
            self._pintar_icone(i, selecionada=(i == indice))
        self.aba_selecionada.emit(self.barra.tabData(indice))
