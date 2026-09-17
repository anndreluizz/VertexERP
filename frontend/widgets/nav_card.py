from PySide6.QtCore import Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from utils.acessibilidade import movimento_reduzido


class NavCard(QFrame):

    clicado = Signal()

    def __init__(
        self,
        titulo,
        subtitulo,
        cor_inicio,
        cor_fim,
        icone_nome=None,
        atalho=None,
        texto_botao=None,
    ):

        super().__init__()

        self.setMinimumHeight(160)
        self.setCursor(Qt.PointingHandCursor)

        self.setStyleSheet(f"""
            QFrame {{
                border-radius: 16px;
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {cor_inicio}, stop:1 {cor_fim}
                );
            }}

            QLabel {{
                border: none;
                background: transparent;
                color: white;
            }}
        """)

        # sombra quase invisivel em repouso e cresce suavemente no
        # hover, com a propria cor do card -- da' uma sensacao de
        # "levantar" o atalho sem precisar redesenhar o gradiente.
        # OBS: blur comeca em 1.0, nunca em 0 -- com blurRadius exato
        # 0 o QGraphicsDropShadowEffect renderiza errado (confirmado
        # via captura offscreen: o card "vaza" por cima do que vem
        # depois dele no layout). 1px de blur e' imperceptivel mas
        # evita esse caso extremo.
        self._sombra = QGraphicsDropShadowEffect(self)
        self._sombra.setBlurRadius(1.0)
        self._sombra.setOffset(0, 0)
        self._sombra.setColor(QColor(cor_inicio))
        self.setGraphicsEffect(self._sombra)

        self._anim_sombra = QVariantAnimation(self)
        self._anim_sombra.setDuration(180)
        self._anim_sombra.valueChanged.connect(self._ao_animar_sombra)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(0)

        topo = QHBoxLayout()
        topo.setSpacing(8)

        if icone_nome:
            from design.icons import icone_pixmap

            self.lbl_icone = QLabel()
            self.lbl_icone.setFixedSize(40, 40)
            self.lbl_icone.setAlignment(Qt.AlignCenter)
            self.lbl_icone.setStyleSheet(
                "background: rgba(255, 255, 255, 0.2); border-radius: 10px;"
            )
            self.lbl_icone.setPixmap(icone_pixmap(icone_nome, cor="#FFFFFF", tamanho=20))
            topo.addWidget(self.lbl_icone)

        topo.addStretch()

        if atalho:
            lbl_atalho = QLabel(f"Atalho: {atalho}")
            lbl_atalho.setStyleSheet("""
                background: rgba(255, 255, 255, 0.18);
                border-radius: 999px;
                font-size: 11px;
                font-weight: 700;
                padding: 4px 10px;
            """)
            topo.addWidget(lbl_atalho, alignment=Qt.AlignTop)

        layout.addLayout(topo)
        layout.addStretch()

        self.lbl_titulo = QLabel(titulo)
        self.lbl_titulo.setStyleSheet(
            "font-size:20px; font-weight:bold;"
        )

        self.lbl_subtitulo = QLabel(subtitulo)
        self.lbl_subtitulo.setWordWrap(True)
        self.lbl_subtitulo.setStyleSheet("font-size:13px;")

        layout.addWidget(self.lbl_titulo)
        layout.addWidget(self.lbl_subtitulo)

        if texto_botao:

            layout.addSpacing(14)

            self.bt_acao = QPushButton(f"{texto_botao}   →")
            self.bt_acao.setCursor(Qt.PointingHandCursor)
            self.bt_acao.setMinimumHeight(34)
            self.bt_acao.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.2);
                    border: none;
                    border-radius: 8px;
                    color: white;
                    font-size: 13px;
                    font-weight: 700;
                    padding: 0 14px;
                    text-align: left;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.32);
                }
            """)
            # o clique no botao tambem conta como clique no card --
            # QPushButton nao propaga mousePressEvent pro pai, entao
            # precisa emitir explicitamente aqui
            self.bt_acao.clicked.connect(self.clicado.emit)

            layout.addWidget(self.bt_acao, alignment=Qt.AlignLeft)

    def _ao_animar_sombra(self, valor):
        self._sombra.setBlurRadius(valor)
        self._sombra.setOffset(0, valor / 3)

    def _animar_sombra_para(self, alvo):
        self._anim_sombra.stop()

        if movimento_reduzido():
            self._ao_animar_sombra(alvo)
            return

        self._anim_sombra.setStartValue(self._sombra.blurRadius())
        self._anim_sombra.setEndValue(alvo)
        self._anim_sombra.start()

    def enterEvent(self, event):
        self._animar_sombra_para(32)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._animar_sombra_para(1.0)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.clicado.emit()
        super().mousePressEvent(event)
