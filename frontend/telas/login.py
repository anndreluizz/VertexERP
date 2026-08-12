import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QCursor, QIcon
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QGraphicsDropShadowEffect,
    QMessageBox,
    QApplication,
)

from requests.exceptions import ConnectionError

from services.api import login
from telas.principal import PrincipalWindow

CAMPO_ESTILO = """
    QLineEdit {
        border: 1px solid #dcdcdc;
        border-radius: 6px;
        padding: 10px 12px;
        font-size: 14px;
        background: #fafafa;
    }
    QLineEdit:focus {
        border: 1px solid #1565C0;
        background: white;
    }
"""

BOTAO_ESTILO = """
    QPushButton {
        background: #1565C0;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 12px;
        font-size: 14px;
        font-weight: bold;
    }
    QPushButton:hover {
        background: #0D47A1;
    }
    QPushButton:disabled {
        background: #90A4AE;
    }
"""


class LoginWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Vertex ERP")
        self.setFixedSize(420, 520)
        self.setStyleSheet("background: #EEF1F5;")

        icone = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "icone.ico",
        )

        if os.path.exists(icone):
            self.setWindowIcon(QIcon(icone))

        self._centralizar()

        layout_externo = QVBoxLayout(self)
        layout_externo.setAlignment(Qt.AlignCenter)

        cartao = QWidget()
        cartao.setObjectName("cartao")
        cartao.setFixedWidth(340)
        cartao.setStyleSheet("""
            QWidget#cartao {
                background: white;
                border-radius: 14px;
            }
        """)

        sombra = QGraphicsDropShadowEffect(self)
        sombra.setBlurRadius(30)
        sombra.setOffset(0, 6)
        sombra.setColor(QColor(0, 0, 0, 50))
        cartao.setGraphicsEffect(sombra)

        layout = QVBoxLayout(cartao)
        layout.setContentsMargins(36, 40, 36, 40)
        layout.setSpacing(0)

        titulo = QLabel("VERTEX ERP")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #1565C0;
        """)

        subtitulo = QLabel("Entrar no sistema")
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setStyleSheet("""
            font-size: 13px;
            color: #757575;
        """)

        self.usuario = QLineEdit()
        self.usuario.setPlaceholderText("E-mail")
        self.usuario.setStyleSheet(CAMPO_ESTILO)

        self.senha = QLineEdit()
        self.senha.setPlaceholderText("Senha")
        self.senha.setEchoMode(QLineEdit.Password)
        self.senha.setStyleSheet(CAMPO_ESTILO)

        self.botao = QPushButton("Entrar")
        self.botao.setCursor(QCursor(Qt.PointingHandCursor))
        self.botao.setStyleSheet(BOTAO_ESTILO)
        self.botao.clicked.connect(self.entrar)

        layout.addWidget(titulo)
        layout.addSpacing(4)
        layout.addWidget(subtitulo)
        layout.addSpacing(28)
        layout.addWidget(self.usuario)
        layout.addSpacing(12)
        layout.addWidget(self.senha)
        layout.addSpacing(24)
        layout.addWidget(self.botao)

        layout_externo.addWidget(cartao)

    def _centralizar(self):
        tela = QApplication.primaryScreen().availableGeometry()
        self.move(
            (tela.width() - self.width()) // 2,
            (tela.height() - self.height()) // 2,
        )

    def entrar(self):

        if not self.usuario.text().strip():

            QMessageBox.warning(
                self,
                "Atenção",
                "Informe o e-mail.",
            )
            return

        if not self.senha.text():

            QMessageBox.warning(
                self,
                "Atenção",
                "Informe a senha.",
            )
            return

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        try:

            ok = login(
                self.usuario.text().strip(),
                self.senha.text(),
            )

            QApplication.restoreOverrideCursor()

            if ok:

                self.principal = PrincipalWindow()
                self.principal.show()
                self.close()

            else:

                QMessageBox.warning(
                    self,
                    "Erro",
                    "Usuário ou senha inválidos.",
                )

        except ConnectionError:

            QApplication.restoreOverrideCursor()

            QMessageBox.critical(
                self,
                "Servidor Offline",
                "Não foi possível conectar ao Backend.\n\n"
                "Verifique se o FastAPI está executando.",
            )

        except Exception as e:

            QApplication.restoreOverrideCursor()

            QMessageBox.critical(
                self,
                "Erro",
                str(e),
            )
