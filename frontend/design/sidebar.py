from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from design.icons import icone, icone_pixmap
from utils.acessibilidade import movimento_reduzido
from design.widgets import Avatar

LARGURA_EXPANDIDA = 248
LARGURA_RECOLHIDA = 76


class ItemMenuLateral(QPushButton):
    """Item de navegação da sidebar: ícone + texto, com barra azul de
    ativo à esquerda e fundo com transição suave no hover — o mesmo
    princípio de "premium" aplicado nos botões, só que ajustado pro
    fundo escuro da lateral."""

    def __init__(self, icone_nome, texto, parent=None):

        super().__init__(parent)

        self.icone_nome = icone_nome
        self.texto_item = texto
        self.recolhido = False

        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(46)
        self.setFont(QFont(tokens.FONTE_FAMILIA_PADRAO, tokens.TAMANHO_MD))

        self._opacidade_fundo = 0.0
        self._anim = QPropertyAnimation(self, b"opacidadeFundo", self)
        self._anim.setDuration(140)

        self.toggled.connect(lambda _: self.update())

    def getOpacidadeFundo(self):
        return self._opacidade_fundo

    def setOpacidadeFundo(self, valor):
        self._opacidade_fundo = valor
        self.update()

    opacidadeFundo = property(getOpacidadeFundo, setOpacidadeFundo)

    def enterEvent(self, event):
        if not self.isChecked():
            self._animar(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.isChecked():
            self._animar(0.0)
        super().leaveEvent(event)

    def _animar(self, destino):
        self._anim.stop()

        if movimento_reduzido():
            self._opacidade_fundo = destino
            self.update()
            return

        self._anim.setStartValue(self._opacidade_fundo)
        self._anim.setEndValue(destino)
        self._anim.start()

    def definir_recolhido(self, recolhido):
        self.recolhido = recolhido
        self.update()

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(8, 0, self.width() - 16, self.height())

        if self.isChecked():
            fundo = QColor(tokens.SIDEBAR_ATIVO)
        elif self._opacidade_fundo > 0:
            fundo = QColor(tokens.SIDEBAR_HOVER)
            fundo.setAlphaF(self._opacidade_fundo)
        else:
            fundo = None

        if fundo:
            painter.setBrush(fundo)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, tokens.RADIUS_SM, tokens.RADIUS_SM)

        if self.isChecked():
            barra = QRectF(0, 10, 3, self.height() - 20)
            painter.setBrush(QColor(tokens.PRIMARIA))
            painter.drawRoundedRect(barra, 1.5, 1.5)

        cor_icone = (
            tokens.TEXTO_CLARO if self.isChecked() else tokens.TEXTO_SIDEBAR
        )

        pixmap = icone_pixmap(self.icone_nome, cor=cor_icone, tamanho=20)
        painter.drawPixmap(24, int(self.height() / 2 - 10), pixmap)

        if not self.recolhido:
            cor_texto = QColor(
                tokens.TEXTO_CLARO if self.isChecked() else tokens.TEXTO_SIDEBAR
            )
            painter.setPen(cor_texto)
            painter.setFont(self.font())
            painter.drawText(
                QRectF(58, 0, self.width() - 70, self.height()),
                Qt.AlignVCenter | Qt.AlignLeft,
                self.texto_item,
            )

        painter.end()


class Sidebar(QFrame):

    item_clicado = Signal(str)
    solicitou_logout = Signal()

    def __init__(self, nome_loja, nome_usuario, cargo, parent=None):

        super().__init__(parent)

        self._recolhida = False

        self.setFixedWidth(LARGURA_EXPANDIDA)
        self.setStyleSheet(f"background:{tokens.SIDEBAR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ======================
        # CABEÇALHO / LOGO
        # ======================

        self.cabecalho = QFrame()
        self.cabecalho.setFixedHeight(84)
        self.cabecalho.setStyleSheet("background:transparent;")

        cab_layout = QHBoxLayout(self.cabecalho)
        cab_layout.setContentsMargins(20, 16, 16, 16)
        cab_layout.setSpacing(12)

        self.marca = QLabel()
        self.marca.setFixedSize(40, 40)
        self.marca.setAlignment(Qt.AlignCenter)
        self.marca.setStyleSheet(f"""
            background: {tokens.PRIMARIA};
            border-radius: {tokens.RADIUS_SM}px;
        """)
        self.marca.setPixmap(icone_pixmap("vertex-mark", cor="#FFFFFF", tamanho=20))

        col_nome = QVBoxLayout()
        col_nome.setSpacing(0)

        self.lbl_titulo = QLabel("VERTEX ERP")
        self.lbl_titulo.setStyleSheet(
            "background:transparent; color:white; font-size:15px; "
            "font-weight:700; letter-spacing: 0.5px;"
        )

        self.lbl_loja = QLabel(nome_loja)
        self.lbl_loja.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_SIDEBAR_APAGADO}; "
            "font-size:11px;"
        )

        col_nome.addWidget(self.lbl_titulo)
        col_nome.addWidget(self.lbl_loja)

        cab_layout.addWidget(self.marca)
        cab_layout.addLayout(col_nome, stretch=1)

        layout.addWidget(self.cabecalho)

        linha_topo = QFrame()
        linha_topo.setFixedHeight(1)
        linha_topo.setStyleSheet(f"background:{tokens.SIDEBAR_HOVER};")
        layout.addWidget(linha_topo)

        # ======================
        # ITENS DE MENU (rolável)
        # ======================

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent; border:none;}"
        )
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        conteudo = QWidget()
        conteudo.setStyleSheet("background:transparent;")

        self.itens_layout = QVBoxLayout(conteudo)
        self.itens_layout.setContentsMargins(0, 12, 0, 12)
        self.itens_layout.setSpacing(2)
        self.itens_layout.setAlignment(Qt.AlignTop)

        scroll.setWidget(conteudo)

        layout.addWidget(scroll, stretch=1)

        self.itens = {}

        # ======================
        # AJUDA + VERSÃO
        # ======================

        self.bloco_ajuda = QFrame()
        self.bloco_ajuda.setStyleSheet("background:transparent;")

        bloco_ajuda_layout = QVBoxLayout(self.bloco_ajuda)
        bloco_ajuda_layout.setContentsMargins(16, 8, 16, 12)
        bloco_ajuda_layout.setSpacing(10)

        self.caixa_ajuda = QFrame()
        self.caixa_ajuda.setStyleSheet(f"""
            QFrame {{
                background: {tokens.SIDEBAR_HOVER};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        ajuda_layout = QVBoxLayout(self.caixa_ajuda)
        ajuda_layout.setContentsMargins(14, 14, 14, 14)
        ajuda_layout.setSpacing(10)

        topo_ajuda = QHBoxLayout()
        topo_ajuda.setSpacing(10)

        icone_ajuda = QLabel()
        icone_ajuda.setFixedSize(32, 32)
        icone_ajuda.setAlignment(Qt.AlignCenter)
        icone_ajuda.setStyleSheet(
            "background: rgba(255, 255, 255, 0.14); border-radius: 10px;"
        )
        icone_ajuda.setPixmap(icone_pixmap("message-circle", cor="#FFFFFF", tamanho=16))
        topo_ajuda.addWidget(icone_ajuda)

        col_ajuda = QVBoxLayout()
        col_ajuda.setSpacing(0)

        lbl_ajuda_titulo = QLabel("Precisa de ajuda?")
        lbl_ajuda_titulo.setStyleSheet(
            "background:transparent; color:white; font-size:12px; font-weight:700;"
        )
        lbl_ajuda_sub = QLabel("Suporte Vertex")
        lbl_ajuda_sub.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_SIDEBAR_APAGADO}; font-size:10.5px;"
        )
        col_ajuda.addWidget(lbl_ajuda_titulo)
        col_ajuda.addWidget(lbl_ajuda_sub)

        topo_ajuda.addLayout(col_ajuda, 1)

        ajuda_layout.addLayout(topo_ajuda)

        bt_falar_agora = QPushButton("Falar agora")
        bt_falar_agora.setCursor(Qt.PointingHandCursor)
        bt_falar_agora.setMinimumHeight(32)
        bt_falar_agora.setStyleSheet(f"""
            QPushButton {{
                background: {tokens.PRIMARIA}; color: white; border: none;
                border-radius: {tokens.RADIUS_SM}px; font-size: 12px; font-weight: 700;
            }}
            QPushButton:hover {{ background: {tokens.PRIMARIA_HOVER}; }}
        """)
        bt_falar_agora.clicked.connect(self._falar_com_suporte)
        ajuda_layout.addWidget(bt_falar_agora)

        bloco_ajuda_layout.addWidget(self.caixa_ajuda)

        self.lbl_versao = QLabel("Vertex ERP · v1.0.0")
        self.lbl_versao.setAlignment(Qt.AlignCenter)
        self.lbl_versao.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_SIDEBAR_APAGADO}; font-size:10.5px;"
        )
        bloco_ajuda_layout.addWidget(self.lbl_versao)

        layout.addWidget(self.bloco_ajuda)

        # ======================
        # RODAPÉ / USUÁRIO
        # ======================

        linha_rodape = QFrame()
        linha_rodape.setFixedHeight(1)
        linha_rodape.setStyleSheet(f"background:{tokens.SIDEBAR_HOVER};")
        layout.addWidget(linha_rodape)

        self.rodape = QFrame()
        self.rodape.setFixedHeight(72)
        self.rodape.setStyleSheet("background:transparent;")

        rodape_layout = QHBoxLayout(self.rodape)
        rodape_layout.setContentsMargins(18, 12, 14, 12)
        rodape_layout.setSpacing(10)

        self.avatar_container = QFrame()
        self.avatar_container.setFixedSize(40, 40)
        self.avatar_container.setStyleSheet("background:transparent;")
        avatar_layout = QVBoxLayout(self.avatar_container)
        avatar_layout.setContentsMargins(0, 0, 0, 0)

        avatar = Avatar(nome_usuario, tamanho=38)
        avatar_layout.addWidget(avatar)

        indicador = QLabel(self.avatar_container)
        indicador.setFixedSize(11, 11)
        indicador.move(28, 28)
        indicador.setStyleSheet(f"""
            background: {tokens.SUCESSO};
            border-radius: 5px;
            border: 2px solid {tokens.SIDEBAR};
        """)

        col_usuario = QVBoxLayout()
        col_usuario.setSpacing(0)

        self.lbl_usuario = QLabel(nome_usuario)
        self.lbl_usuario.setStyleSheet(
            "background:transparent; color:white; font-size:12px; "
            "font-weight:600;"
        )

        self.lbl_cargo = QLabel(cargo)
        self.lbl_cargo.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_SIDEBAR_APAGADO}; "
            "font-size:11px;"
        )

        col_usuario.addWidget(self.lbl_usuario)
        col_usuario.addWidget(self.lbl_cargo)

        rodape_layout.addWidget(self.avatar_container)
        rodape_layout.addLayout(col_usuario, stretch=1)

        self.bt_recolher = QPushButton()
        self.bt_recolher.setFixedSize(28, 28)
        self.bt_recolher.setCursor(Qt.PointingHandCursor)
        self.bt_recolher.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                border:none;
                border-radius:6px;
            }}
            QPushButton:hover {{
                background: {tokens.SIDEBAR_HOVER};
            }}
        """)
        self.bt_recolher.setIcon(
            icone("chevron-left", cor=tokens.TEXTO_SIDEBAR, tamanho=16)
        )
        self.bt_recolher.setIconSize(QSize(16, 16))
        self.bt_recolher.clicked.connect(self.alternar_recolhida)

        rodape_layout.addWidget(self.bt_recolher)

        layout.addWidget(self.rodape)

        self._anim_largura = QPropertyAnimation(self, b"minimumWidth", self)
        self._anim_largura.setDuration(200)
        self._anim_largura.setEasingCurve(QEasingCurve.OutCubic)

        self._anim_largura_max = QPropertyAnimation(self, b"maximumWidth", self)
        self._anim_largura_max.setDuration(200)
        self._anim_largura_max.setEasingCurve(QEasingCurve.OutCubic)

    def definir_nome_loja(self, nome_loja):
        self.lbl_loja.setText(nome_loja)

    def adicionar_item(self, chave, icone_nome, texto):

        item = ItemMenuLateral(icone_nome, texto)
        item.clicked.connect(lambda: self._selecionar(chave))

        self.itens_layout.addWidget(item)
        self.itens[chave] = item

        return item

    def selecionar(self, chave):
        self._selecionar(chave, emitir=False)

    def _selecionar(self, chave, emitir=True):

        for nome, item in self.itens.items():
            item.setChecked(nome == chave)

        if emitir:
            self.item_clicado.emit(chave)

    def alternar_recolhida(self):

        self._recolhida = not self._recolhida

        largura = LARGURA_RECOLHIDA if self._recolhida else LARGURA_EXPANDIDA

        for anim in (self._anim_largura, self._anim_largura_max):
            anim.stop()

        if movimento_reduzido():
            self.setMinimumWidth(largura)
            self.setMaximumWidth(largura)
        else:
            for anim in (self._anim_largura, self._anim_largura_max):
                anim.setStartValue(self.width())
                anim.setEndValue(largura)
                anim.start()

        self.lbl_titulo.setVisible(not self._recolhida)
        self.lbl_loja.setVisible(not self._recolhida)
        self.lbl_usuario.setVisible(not self._recolhida)
        self.lbl_cargo.setVisible(not self._recolhida)
        self.bloco_ajuda.setVisible(not self._recolhida)

        nome_seta = "chevron-right" if self._recolhida else "chevron-left"
        self.bt_recolher.setIcon(icone(nome_seta, cor=tokens.TEXTO_SIDEBAR, tamanho=16))

        for item in self.itens.values():
            item.definir_recolhido(self._recolhida)

    def _falar_com_suporte(self):

        # nenhum canal de suporte de verdade esta configurado ainda
        # (sem numero/whatsapp/e-mail fixo pra empresa) -- melhor essa
        # mensagem honesta do que inventar um contato que nao existe
        QMessageBox.information(
            self,
            "Precisa de ajuda?",
            "Fale com o administrador do seu sistema pra tirar dúvidas "
            "ou reportar um problema.",
        )
