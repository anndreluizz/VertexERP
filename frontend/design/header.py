from datetime import datetime

from PySide6.QtCore import QSize, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from design.icons import icone
from design.widgets import Avatar


class _Popover(QWidget):
    """Base de um painel flutuante abaixo de um botão do header (usado
    tanto pra notificações quanto pro menu de perfil) — Qt.Popup fecha
    sozinho ao clicar fora, sem precisar reimplementar isso na mão."""

    def __init__(self, largura=280):

        super().__init__(None, Qt.Popup)

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(largura)

        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)

        self.corpo = QFrame()
        self.corpo.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        externo.addWidget(self.corpo)

        self.layout_corpo = QVBoxLayout(self.corpo)
        self.layout_corpo.setContentsMargins(4, 4, 4, 4)
        self.layout_corpo.setSpacing(2)

    def abrir_sob(self, botao):

        ponto = botao.mapToGlobal(botao.rect().bottomRight())
        self.move(ponto.x() - self.width(), ponto.y() + 8)
        self.show()


class _BlocoClicavel(QFrame):
    """QFrame ao invés de QPushButton de propósito: QPushButton.sizeHint()
    ignora o layout filho e trunca o conteúdo — QFrame com layout dimensiona
    certo e ainda aceita :hover via QSS normalmente."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class _ItemMenu(QPushButton):

    def __init__(self, texto, icone_nome=None, perigo=False):

        super().__init__(texto)

        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)

        if icone_nome:
            self.setIcon(icone(
                icone_nome,
                cor=tokens.ERRO if perigo else tokens.TEXTO_SECUNDARIO,
                tamanho=16,
            ))

        cor_texto = tokens.ERRO if perigo else tokens.TEXTO

        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding-left: 10px;
                border: none;
                border-radius: {tokens.RADIUS_SM}px;
                color: {cor_texto};
                font-size: {tokens.TAMANHO_MD}px;
                background: transparent;
            }}
            QPushButton:hover {{
                background: {tokens.FUNDO};
            }}
        """)


class Header(QFrame):

    busca_alterada = Signal(str)
    tema_alternado = Signal(bool)
    solicitou_logout = Signal()
    solicitou_trocar_senha = Signal()

    def __init__(self, nome_loja, nome_usuario, cargo, parent=None):

        super().__init__(parent)

        # reflete o tema que ja esta ativo (ver design.tokens.aplicar,
        # chamado no arranque do app) -- sem isso o botao sempre
        # nascia mostrando o icone de "mudar pra escuro" mesmo quando
        # o escuro ja estava ligado
        self._modo_escuro = tokens.ESCURO_ATIVO

        self.setFixedHeight(64)
        self.setStyleSheet(f"""
            Header {{
                background: {tokens.CARD};
                border-bottom: 1px solid {tokens.BORDA};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 20, 0)
        layout.setSpacing(16)

        self.lbl_titulo = QLabel("Início")
        self.lbl_titulo.setStyleSheet(f"""
            background: transparent;
            color: {tokens.TEXTO};
            font-size: {tokens.TAMANHO_XL}px;
            font-weight: 700;
        """)
        layout.addWidget(self.lbl_titulo)

        # ======================
        # BUSCA GLOBAL
        # ======================

        busca_container = QFrame()
        busca_container.setFixedHeight(38)
        busca_container.setMinimumWidth(280)
        busca_container.setStyleSheet(f"""
            QFrame {{
                background: {tokens.FUNDO};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

        busca_layout = QHBoxLayout(busca_container)
        busca_layout.setContentsMargins(10, 0, 10, 0)
        busca_layout.setSpacing(6)

        lbl_lupa = QLabel()
        lbl_lupa.setPixmap(
            icone(
                "search", cor=tokens.TEXTO_TERCIARIO, tamanho=16
            ).pixmap(16, 16)
        )
        lbl_lupa.setStyleSheet("background:transparent;")

        self.campo_busca = QLineEdit()
        self.campo_busca.setPlaceholderText("Buscar produtos, clientes, vendas...")
        self.campo_busca.setStyleSheet(f"""
            QLineEdit {{
                border: none;
                background: transparent;
                color: {tokens.TEXTO};
                font-size: {tokens.TAMANHO_BASE}px;
            }}
        """)
        self.campo_busca.textChanged.connect(self.busca_alterada)

        busca_layout.addWidget(lbl_lupa)
        busca_layout.addWidget(self.campo_busca, stretch=1)

        layout.addWidget(busca_container, stretch=1)

        # ======================
        # RELÓGIO
        # ======================

        self.lbl_relogio = QLabel()
        self.lbl_relogio.setStyleSheet(f"""
            background: transparent;
            color: {tokens.TEXTO_SECUNDARIO};
            font-size: {tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(self.lbl_relogio)

        self._timer_relogio = QTimer(self)
        self._timer_relogio.timeout.connect(self._atualizar_relogio)
        self._timer_relogio.start(1000)
        self._atualizar_relogio()

        # ======================
        # TEMA / NOTIFICAÇÕES / PERFIL
        # ======================

        self.bt_tema = self._botao_icone(
            "sun" if self._modo_escuro else "moon"
        )
        self.bt_tema.setToolTip("Alternar tema claro/escuro")
        self.bt_tema.clicked.connect(self._alternar_tema)
        layout.addWidget(self.bt_tema)

        self.bt_notificacoes = self._botao_icone("bell")
        self.bt_notificacoes.setToolTip("Notificações")
        self.bt_notificacoes.clicked.connect(self._abrir_notificacoes)
        layout.addWidget(self.bt_notificacoes)

        divisor = QFrame()
        divisor.setFixedSize(1, 32)
        divisor.setStyleSheet(f"background:{tokens.BORDA};")
        layout.addWidget(divisor)

        self.bt_perfil = _BlocoClicavel()
        self.bt_perfil.setFixedHeight(44)
        self.bt_perfil.setStyleSheet(f"""
            _BlocoClicavel {{
                border: none;
                border-radius: {tokens.RADIUS_SM}px;
                background: transparent;
            }}
            _BlocoClicavel:hover {{
                background: {tokens.FUNDO};
            }}
        """)

        perfil_layout = QHBoxLayout(self.bt_perfil)
        perfil_layout.setContentsMargins(8, 0, 12, 0)
        perfil_layout.setSpacing(8)

        avatar = Avatar(nome_usuario, tamanho=34)
        perfil_layout.addWidget(avatar)

        col_perfil = QVBoxLayout()
        col_perfil.setSpacing(0)

        lbl_nome = QLabel(nome_usuario)
        lbl_nome.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)

        lbl_cargo = QLabel(cargo)
        lbl_cargo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_perfil.addWidget(lbl_nome)
        col_perfil.addWidget(lbl_cargo)

        perfil_layout.addLayout(col_perfil)

        self.bt_perfil.clicked.connect(self._abrir_menu_perfil)

        layout.addWidget(self.bt_perfil)

        self._popover_notificacoes = None
        self._popover_perfil = None

    def _botao_icone(self, nome_icone):

        botao = QPushButton()
        botao.setFixedSize(38, 38)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setIcon(icone(nome_icone, cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
        botao.setIconSize(QSize(18, 18))
        botao.setStyleSheet(f"""
            QPushButton {{
                border: none;
                border-radius: {tokens.RADIUS_SM}px;
                background: transparent;
            }}
            QPushButton:hover {{
                background: {tokens.FUNDO};
            }}
        """)
        return botao

    def definir_titulo(self, texto):
        self.lbl_titulo.setText(texto)

    def _atualizar_relogio(self):
        agora = datetime.now()
        dias = [
            "segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo",
        ]
        self.lbl_relogio.setText(
            f"{dias[agora.weekday()]}, {agora.strftime('%d/%m/%Y')} · "
            f"{agora.strftime('%H:%M:%S')}"
        )

    def _alternar_tema(self):
        self._modo_escuro = not self._modo_escuro
        self.bt_tema.setIcon(
            icone(
                "sun" if self._modo_escuro else "moon",
                cor=tokens.TEXTO_SECUNDARIO,
                tamanho=18,
            )
        )
        self.tema_alternado.emit(self._modo_escuro)

    def _abrir_notificacoes(self):

        popover = _Popover(largura=300)

        titulo = QLabel("Notificações")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:700;
            padding: 8px 10px 4px 10px;
        """)
        popover.layout_corpo.addWidget(titulo)

        vazio = QLabel("Nenhuma notificação por enquanto.")
        vazio.setWordWrap(True)
        vazio.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; padding: 4px 10px 12px 10px;
        """)
        popover.layout_corpo.addWidget(vazio)

        self._popover_notificacoes = popover
        popover.abrir_sob(self.bt_notificacoes)

    def _abrir_menu_perfil(self):

        popover = _Popover(largura=200)

        item_senha = _ItemMenu("Trocar Senha", icone_nome="lock")
        item_senha.clicked.connect(popover.close)
        item_senha.clicked.connect(self.solicitou_trocar_senha)

        item_sair = _ItemMenu("Sair", icone_nome="log-out", perigo=True)
        item_sair.clicked.connect(popover.close)
        item_sair.clicked.connect(self.solicitou_logout)

        popover.layout_corpo.addWidget(item_senha)
        popover.layout_corpo.addWidget(item_sair)

        self._popover_perfil = popover
        popover.abrir_sob(self.bt_perfil)
