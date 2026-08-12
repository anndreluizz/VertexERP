from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QVBoxLayout,
    QProgressBar,
)


class LoadingDialog(QDialog):

    def __init__(
        self,
        texto="Processando..."
    ):
        super().__init__()

        self.setWindowTitle("Vertex ERP")

        self.setFixedSize(320, 120)

        self.setWindowFlag(
            Qt.WindowContextHelpButtonHint,
            False
        )

        self.setModal(True)

        layout = QVBoxLayout(self)

        self.label = QLabel(texto)

        self.label.setAlignment(Qt.AlignCenter)

        self.label.setStyleSheet("""
            font-size:16px;
            font-weight:bold;
        """)

        layout.addWidget(self.label)

        self.progress = QProgressBar()

        self.progress.setRange(0, 0)

        layout.addWidget(self.progress)

    def alterar_texto(
        self,
        texto
    ):

        self.label.setText(texto)