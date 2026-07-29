from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QMessageBox,
    QApplication,
)

from requests.exceptions import ConnectionError

from services.api import cadastrar_usuario, login


class CadastroInicialWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Vertex ERP - Primeiro Acesso")
        self.setFixedSize(460, 620)
        self.setStyleSheet("background:#f4f5f7;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 60, 50, 40)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignTop)

        titulo = QLabel("Comece Agora")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(
            "background:transparent; font-size:28px; "
            "font-weight:bold; color:#202225;"
        )

        subtitulo = QLabel("CRIE SUA CONTA NO VERTEX ERP")
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:#9E9E9E;"
        )

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(24)

        self.nome = self._campo(layout, "NOME COMPLETO", "Seu nome")
        self.email = self._campo(
            layout, "E-MAIL", "seu@email.com"
        )
        self.senha = self._campo(
            layout, "SENHA", "••••••", senha=True
        )
        self.confirmar = self._campo(
            layout, "CONFIRMAR SENHA", "••••••", senha=True
        )

        layout.addSpacing(10)

        self.termos = QCheckBox(
            "Eu aceito os Termos e Política de Privacidade"
        )
        self.termos.setStyleSheet("""
            QCheckBox {
                background:transparent; font-size:12px; color:#616161;
                spacing:8px;
            }
            QCheckBox::indicator {
                width:18px; height:18px; border-radius:4px;
                border:1.5px solid #9E9E9E; background:#ffffff;
            }
            QCheckBox::indicator:checked {
                border:1.5px solid #1565C0; background:#1565C0;
                image: none;
            }
        """)
        self.termos.stateChanged.connect(self._validar)

        layout.addWidget(self.termos)
        layout.addSpacing(16)

        self.bt_criar = QPushButton("CRIAR CONTA")
        self.bt_criar.setMinimumHeight(48)
        self.bt_criar.setEnabled(False)
        self.bt_criar.clicked.connect(self.criar_conta)

        layout.addWidget(self.bt_criar)
        layout.addSpacing(14)

        rodape = QHBoxLayout()
        rodape.setAlignment(Qt.AlignCenter)

        lbl_rodape = QLabel("Já tem uma conta?")
        lbl_rodape.setStyleSheet(
            "background:transparent; font-size:12px; color:#616161;"
        )

        bt_acessar = QPushButton("Acessar minha conta")
        bt_acessar.setStyleSheet("""
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
        bt_acessar.clicked.connect(self.ir_para_login)

        rodape.addWidget(lbl_rodape)
        rodape.addWidget(bt_acessar)

        layout.addLayout(rodape)

        self._atualizar_estilo_botao()

        self.nome.setFocus()

    # ======================================

    def _campo(self, layout, rotulo, placeholder, senha=False):

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(
            "background:transparent; font-size:10px; "
            "font-weight:bold; color:#757575; margin-top:8px;"
        )

        campo = QLineEdit()
        campo.setPlaceholderText(placeholder)
        campo.setMinimumHeight(42)
        campo.setStyleSheet("""
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

        if senha:
            campo.setEchoMode(QLineEdit.Password)

        campo.textChanged.connect(self._validar)

        layout.addWidget(lbl)
        layout.addWidget(campo)

        return campo

    def _validar(self):

        valido = (
            bool(self.nome.text().strip())
            and bool(self.email.text().strip())
            and bool(self.senha.text())
            and self.senha.text() == self.confirmar.text()
            and self.termos.isChecked()
        )

        self.bt_criar.setEnabled(valido)
        self._atualizar_estilo_botao()

    def _atualizar_estilo_botao(self):

        if self.bt_criar.isEnabled():
            self.bt_criar.setStyleSheet("""
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
        else:
            self.bt_criar.setStyleSheet("""
                QPushButton {
                    background:#c4c6c9;
                    color:white;
                    font-weight:bold;
                    border-radius:10px;
                }
            """)

    # ======================================

    def criar_conta(self):

        nome = self.nome.text().strip()
        email = self.email.text().strip()
        senha = self.senha.text()

        if senha != self.confirmar.text():
            QMessageBox.warning(
                self, "Atenção", "As senhas não coincidem."
            )
            return

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        try:

            response = cadastrar_usuario(nome, email, senha)

            if response.status_code != 200:

                QApplication.restoreOverrideCursor()

                try:
                    erro = response.json().get("detail") or str(
                        response.json()
                    )
                except Exception:
                    erro = response.text

                QMessageBox.critical(self, "Erro", str(erro))
                return

            # so o primeirissimo usuario do sistema (a loja ainda nem
            # tem nome) nasce admin - so nesse caso faz sentido pedir
            # pra configurar a loja logo em seguida
            eh_primeiro_usuario = (
                response.json().get("data", {}).get("admin", False)
            )

            if not login(email, senha):

                QApplication.restoreOverrideCursor()

                QMessageBox.critical(
                    self,
                    "Erro",
                    "Conta criada, mas não foi possível entrar "
                    "automaticamente. Tente acessar manualmente.",
                )
                return

            QApplication.restoreOverrideCursor()

            if eh_primeiro_usuario:

                from telas.cadastrar_loja import CadastrarLojaDialog

                self.dialogo_loja = CadastrarLojaDialog()
                self.dialogo_loja.loja_salva.connect(
                    self.abrir_sistema
                )
                self.dialogo_loja.show()

            else:

                self.abrir_sistema()

            self.close()

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

            QMessageBox.critical(self, "Erro", str(e))

    def abrir_sistema(self):

        from telas.principal import PrincipalWindow

        self.principal = PrincipalWindow()
        self.principal.show()

    def ir_para_login(self):

        from telas.login import LoginWindow

        self.login = LoginWindow()
        self.login.show()
        self.close()
