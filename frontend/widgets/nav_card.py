from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class NavCard(QFrame):

    clicado = Signal()

    def __init__(self, titulo, subtitulo, cor_inicio, cor_fim, icone_nome=None):

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)

        if icone_nome:
            from design.icons import icone_pixmap

            self.lbl_icone = QLabel()
            self.lbl_icone.setFixedSize(40, 40)
            self.lbl_icone.setAlignment(Qt.AlignCenter)
            self.lbl_icone.setStyleSheet(
                "background: rgba(255, 255, 255, 0.2); border-radius: 10px;"
            )
            self.lbl_icone.setPixmap(icone_pixmap(icone_nome, cor="#FFFFFF", tamanho=20))
            layout.addWidget(self.lbl_icone)

        self.lbl_titulo = QLabel(titulo)
        self.lbl_titulo.setStyleSheet(
            "font-size:20px; font-weight:bold;"
        )

        self.lbl_subtitulo = QLabel(subtitulo)
        self.lbl_subtitulo.setStyleSheet("font-size:13px;")

        layout.addStretch()
        layout.addWidget(self.lbl_titulo)
        layout.addWidget(self.lbl_subtitulo)

    def mousePressEvent(self, event):
        self.clicado.emit()
        super().mousePressEvent(event)
