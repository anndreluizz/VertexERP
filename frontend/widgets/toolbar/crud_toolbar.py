from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
)

from design import tokens


class CrudToolbar(QWidget):

    novo = Signal()
    editar = Signal()
    excluir = Signal()
    atualizar = Signal()

    def __init__(self):
        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.bt_novo = QPushButton("➕ Novo")
        self.bt_editar = QPushButton("✏️ Editar")
        self.bt_excluir = QPushButton("🗑 Excluir")
        self.bt_atualizar = QPushButton("🔄 Atualizar")

        self._configurar_botao(
            self.bt_novo,
            tokens.SECUNDARIA,
            tokens.SECUNDARIA_HOVER,
        )

        self._configurar_botao(
            self.bt_editar,
            tokens.PRIMARIA,
            tokens.PRIMARIA_HOVER,
        )

        self._configurar_botao(
            self.bt_excluir,
            tokens.ERRO,
            tokens.ERRO_HOVER,
        )

        self._configurar_botao(
            self.bt_atualizar,
            tokens.SIDEBAR,
            tokens.SIDEBAR_HOVER,
        )

        layout.addWidget(self.bt_novo)
        layout.addWidget(self.bt_editar)
        layout.addWidget(self.bt_excluir)

        layout.addStretch()

        layout.addWidget(self.bt_atualizar)

        self.bt_novo.clicked.connect(self.novo.emit)
        self.bt_editar.clicked.connect(self.editar.emit)
        self.bt_excluir.clicked.connect(self.excluir.emit)
        self.bt_atualizar.clicked.connect(self.atualizar.emit)

    def _configurar_botao(
        self,
        botao,
        cor,
        hover,
    ):

        botao.setMinimumHeight(36)

        botao.setStyleSheet(f"""
            QPushButton {{
                background:{cor};
                color:white;
                font-weight:bold;
                border:none;
                border-radius:6px;
                padding:6px 14px;
            }}

            QPushButton:hover {{
                background:{hover};
            }}
        """)

    def habilitar_edicao(self, habilitado=True):

        self.bt_editar.setEnabled(habilitado)
        self.bt_excluir.setEnabled(habilitado)

    def mostrar_atualizar(self, mostrar=True):

        self.bt_atualizar.setVisible(mostrar)