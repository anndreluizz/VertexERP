from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout, QVBoxLayout


class Banner(QFrame):

    clicado = Signal()

    def __init__(self, categoria, titulo, icone, cor):

        super().__init__()

        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(64)

        self.setStyleSheet(f"""
            QFrame {{
                background: {cor};
                border-radius: 12px;
            }}

            QLabel {{
                border: none;
                background: transparent;
                color: white;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(0)

        lbl_categoria = QLabel(categoria)
        lbl_categoria.setStyleSheet(
            "font-size:10px; font-weight:bold;"
        )

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(
            "font-size:15px; font-weight:bold;"
        )

        col_texto.addWidget(lbl_categoria)
        col_texto.addWidget(lbl_titulo)

        lbl_icone = QLabel(icone)
        lbl_icone.setFixedSize(36, 36)
        lbl_icone.setAlignment(Qt.AlignCenter)
        lbl_icone.setStyleSheet("""
            background: rgba(255, 255, 255, 40);
            border-radius: 18px;
            font-size: 16px;
        """)

        layout.addLayout(col_texto)
        layout.addStretch()
        layout.addWidget(lbl_icone)

    def mousePressEvent(self, event):
        self.clicado.emit()
        super().mousePressEvent(event)
