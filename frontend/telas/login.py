from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
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
        self.setFixedSize(460, 560)
        self.setStyleSheet("background:#f4f5f7;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 70, 50, 40)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignTop)

        titulo = QLabel("VERTEX ERP")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(
            "background:transparent; font-size:28px; "
            "font-weight:bold; color:#202225;"
        )

        subtitulo = QLabel("GESTÃO E PDV PROFISSIONAL")
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:#9E9E9E;"
        )

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(30)

        lbl_email = QLabel("E-MAIL")
        lbl_email.setStyleSheet(
            "background:transparent; font-size:10px; "
            "font-weight:bold; color:#757575;"
        )

        self.usuario = QLineEdit()
        self.usuario.setPlaceholderText("seu@contato.com")
        self.usuario.setMinimumHeight(44)
        self.usuario.setStyleSheet("""
            QLineEdit {
                background:#eef0f3;
                border:1px solid #eef0f3;
                border-radius:10px;
                padding:0 14px;
                font-size:13px;
                color:#202225;
            }
            QLineEdit:focus {
                border:1px solid #1565C0;
                background:white;
            }
        """)

        layout.addWidget(lbl_email)
        layout.addWidget(self.usuario)
        layout.addSpacing(14)

        lbl_senha = QLabel("SENHA")
        lbl_senha.setStyleSheet(
            "background:transparent; font-size:10px; "
            "font-weight:bold; color:#757575;"
        )

        layout.addWidget(lbl_senha)

        campo_senha = QFrame()
        campo_senha.setStyleSheet("""
            QFrame {
                background:#eef0f3;
                border:1px solid #eef0f3;
                border-radius:10px;
            }
        """)
        campo_senha_layout = QHBoxLayout(campo_senha)
        campo_senha_layout.setContentsMargins(14, 0, 8, 0)
        campo_senha_layout.setSpacing(4)

        self.senha = QLineEdit()
        self.senha.setPlaceholderText("••••••••")
        self.senha.setMinimumHeight(44)
        self.senha.setEchoMode(QLineEdit.Password)
        self.senha.setStyleSheet("""
            QLineEdit {
                background:transparent;
                border:none;
                font-size:13px;
                color:#202225;
            }
        """)
        self.senha.returnPressed.connect(self.entrar)

        self.bt_ver_senha = QPushButton("👁")
        self.bt_ver_senha.setFixedSize(30, 30)
        self.bt_ver_senha.setAutoDefault(False)
        self.bt_ver_senha.setCheckable(True)
        self.bt_ver_senha.setStyleSheet("""
            QPushButton {
                background:transparent;
                border:none;
                font-size:14px;
            }
        """)
        self.bt_ver_senha.clicked.connect(self.alternar_ver_senha)

        campo_senha_layout.addWidget(self.senha)
        campo_senha_layout.addWidget(self.bt_ver_senha)

        layout.addWidget(campo_senha)
        layout.addSpacing(10)

        linha_opcoes = QHBoxLayout()

        self.manter_conectado = QCheckBox("Manter conectado")
        self.manter_conectado.setChecked(True)
        self.manter_conectado.setStyleSheet(
            "background:transparent; font-size:12px; color:#616161;"
        )

        bt_esqueceu = QPushButton("Esqueceu a senha?")
        bt_esqueceu.setAutoDefault(False)
        bt_esqueceu.setStyleSheet("""
            QPushButton {
                background:transparent;
                border:none;
                color:#1565C0;
                font-size:12px;
                font-weight:bold;
            }
            QPushButton:hover {
                color:#0D47A1;
            }
        """)
        bt_esqueceu.clicked.connect(self.esqueceu_senha)

        linha_opcoes.addWidget(self.manter_conectado)
        linha_opcoes.addStretch()
        linha_opcoes.addWidget(bt_esqueceu)

        layout.addLayout(linha_opcoes)
        layout.addSpacing(20)

        self.botao = QPushButton("ACESSAR SISTEMA")
        self.botao.setMinimumHeight(48)
        self.botao.setStyleSheet("""
            QPushButton {
                background:#202225;
                color:white;
                font-weight:bold;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#33363b;
            }
        """)
        self.botao.clicked.connect(self.entrar)

        layout.addWidget(self.botao)
        layout.addSpacing(14)

        rodape = QHBoxLayout()
        rodape.setAlignment(Qt.AlignCenter)

        lbl_rodape = QLabel("Precisa de uma nova conta?")
        lbl_rodape.setStyleSheet(
            "background:transparent; font-size:12px; color:#616161;"
        )

        bt_cadastrar = QPushButton("Cadastre-se")
        bt_cadastrar.setAutoDefault(False)
        bt_cadastrar.setStyleSheet("""
            QPushButton {
                background:transparent;
                border:none;
                color:#1565C0;
                font-size:12px;
                font-weight:bold;
            }
            QPushButton:hover {
                color:#0D47A1;
            }
        """)
        bt_cadastrar.clicked.connect(self.ir_para_cadastro)

        rodape.addWidget(lbl_rodape)
        rodape.addWidget(bt_cadastrar)

        layout.addLayout(rodape)
        layout.addStretch()

        self.usuario.setFocus()

    # ======================================

    def ir_para_cadastro(self):

        from telas.cadastro_inicial import CadastroInicialWindow

        self.cadastro = CadastroInicialWindow()
        self.cadastro.show()
        self.close()

    def alternar_ver_senha(self):

        if self.bt_ver_senha.isChecked():
            self.senha.setEchoMode(QLineEdit.Normal)
        else:
            self.senha.setEchoMode(QLineEdit.Password)

    def esqueceu_senha(self):

        QMessageBox.information(
            self,
            "Esqueceu a senha?",
            "Entre em contato com o suporte pra redefinir sua senha.",
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
