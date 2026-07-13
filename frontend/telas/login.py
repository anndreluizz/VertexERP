from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QMessageBox,
    QApplication,
)

from requests.exceptions import ConnectionError

from services.api import login
from telas.principal import PrincipalWindow


class LoginWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Vertex ERP")
        self.setFixedSize(350, 220)

        layout = QVBoxLayout()

        titulo = QLabel("VERTEX ERP")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            font-size:22px;
            font-weight:bold;
        """)

        self.usuario = QLineEdit()
        self.usuario.setPlaceholderText("E-mail")

        self.senha = QLineEdit()
        self.senha.setPlaceholderText("Senha")
        self.senha.setEchoMode(QLineEdit.Password)

        self.botao = QPushButton("Entrar")
        self.botao.clicked.connect(self.entrar)

        layout.addWidget(titulo)
        layout.addSpacing(15)
        layout.addWidget(self.usuario)
        layout.addWidget(self.senha)
        layout.addSpacing(10)
        layout.addWidget(self.botao)

        self.setLayout(layout)

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