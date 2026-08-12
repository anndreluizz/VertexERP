from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QVBoxLayout,
)


class Card(QFrame):

    def __init__(self, titulo, valor, cor="#1565C0", variacao=None, ao_clicar=None):

        super().__init__()

        self._ao_clicar = ao_clicar

        self.setObjectName("card")
        self.setMinimumHeight(130)

        # Sem isso, numa janela larga o grid estica cada card pra
        # preencher o espaço todo — cards enormes e desproporcionais em
        # vez de continuar num tamanho de cartão normal.
        self.setMaximumWidth(340)

        self.setStyleSheet(f"""
            QFrame#card{{
                background:white;
                border-radius:12px;
                border:1px solid #dcdcdc;
                border-left:5px solid {cor};
            }}

            QLabel{{
                border:none;
                background:transparent;
            }}
        """)

        sombra = QGraphicsDropShadowEffect(self)
        sombra.setBlurRadius(18)
        sombra.setOffset(0, 3)
        sombra.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(sombra)

        layout = QVBoxLayout(self)

        self.titulo = QLabel(titulo)
        self.titulo.setAlignment(Qt.AlignCenter)

        self.valor = QLabel(str(valor))
        self.valor.setAlignment(Qt.AlignCenter)

        self.titulo.setStyleSheet("""
            font-size:15px;
            color:gray;
        """)

        self.valor.setStyleSheet(f"""
            font-size:28px;
            font-weight:bold;
            color:{cor};
        """)

        layout.addStretch()
        layout.addWidget(self.titulo)
        layout.addWidget(self.valor)

        self.variacao_label = None

        if variacao is not None:
            self.variacao_label = QLabel(self._texto_variacao(variacao))
            self.variacao_label.setAlignment(Qt.AlignCenter)
            self.variacao_label.setStyleSheet(
                "font-size:13px; font-weight:bold; color:%s;"
                % ("#2E7D32" if variacao >= 0 else "#C62828")
            )
            layout.addWidget(self.variacao_label)

        layout.addStretch()

        if ao_clicar is not None:
            self.setCursor(QCursor(Qt.PointingHandCursor))

    def _texto_variacao(self, variacao):
        seta = "▲" if variacao >= 0 else "▼"
        return f"{seta} {abs(variacao):.0f}% vs ontem"

    def mousePressEvent(self, event):

        if self._ao_clicar is not None:
            self._ao_clicar()

        super().mousePressEvent(event)

    def atualizar(self, valor):

        self.valor.setText(str(valor))
