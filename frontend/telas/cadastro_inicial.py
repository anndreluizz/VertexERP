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

from services.api import cadastrar_usuario, login, me, configuracoes
from services.worker import rodar_em_thread, em_paralelo


def _criar_conta_e_logar(nome, email, senha):
    """Roda na worker thread -- cadastro do primeiro/novo usuario
    seguido de login automatico com a mesma credencial."""

    response = cadastrar_usuario(nome, email, senha)

    if response.status_code != 200:
        return response, None

    eh_primeiro_usuario = response.json().get("data", {}).get("admin", False)
    ok, erro_login, _verificacao_id = login(email, senha)

    return response, (eh_primeiro_usuario, ok, erro_login)
from design import tokens
from design.responsive import tamanho_fixo_seguro
from utils.validacao import email_valido


def _buscar_info_principal():
    """Roda na worker thread -- mesmo raciocinio de
    telas/login.py::_buscar_info_principal (duplicado aqui de proposito
    em vez de importar de lá, pra nao criar acoplamento entre as duas
    telas de entrada por causa de uma funcao de 1 linha). As duas sao
    independentes, entao disparam em paralelo."""
    return em_paralelo((me,), (configuracoes,))


class CadastroInicialWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Vertex ERP - Primeiro Acesso")
        tamanho_fixo_seguro(self, 460, 620)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 60, 50, 40)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignTop)

        titulo = QLabel("Comece Agora")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(
            f"background:transparent; font-size:28px; "
            f"font-weight:bold; color:{tokens.TEXTO};"
        )

        subtitulo = QLabel("CRIE SUA CONTA NO VERTEX ERP")
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setStyleSheet(
            f"background:transparent; font-size:11px; "
            f"font-weight:bold; color:{tokens.TEXTO_TERCIARIO};"
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
        self.termos.setStyleSheet(f"""
            QCheckBox {{
                background:transparent; font-size:12px; color:{tokens.TEXTO_SECUNDARIO};
                spacing:8px;
            }}
            QCheckBox::indicator {{
                width:18px; height:18px; border-radius:4px;
                border:1.5px solid {tokens.TEXTO_TERCIARIO}; background:{tokens.CARD};
            }}
            QCheckBox::indicator:checked {{
                border:1.5px solid {tokens.PRIMARIA}; background:{tokens.PRIMARIA};
                image: none;
            }}
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
            f"background:transparent; font-size:12px; color:{tokens.TEXTO_SECUNDARIO};"
        )

        bt_acessar = QPushButton("Acessar minha conta")
        bt_acessar.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                border:none;
                color:{tokens.PRIMARIA};
                font-size:12px;
                font-weight:bold;
            }}
            QPushButton:hover {{
                color:{tokens.PRIMARIA_HOVER};
            }}
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
            f"background:transparent; font-size:10px; "
            f"font-weight:bold; color:{tokens.TEXTO_TERCIARIO}; margin-top:8px;"
        )

        campo = QLineEdit()
        campo.setPlaceholderText(placeholder)
        campo.setMinimumHeight(42)
        campo.setStyleSheet(f"""
            QLineEdit {{
                background:{tokens.FUNDO};
                border:1px solid {tokens.FUNDO};
                border-radius:10px;
                padding:0 14px;
                font-size:13px;
                color:{tokens.TEXTO};
            }}
            QLineEdit:focus {{
                border:1px solid {tokens.PRIMARIA};
                background:{tokens.CARD};
            }}
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
            and email_valido(self.email.text())
            and bool(self.senha.text())
            and self.senha.text() == self.confirmar.text()
            and self.termos.isChecked()
        )

        self.bt_criar.setEnabled(valido)
        self._atualizar_estilo_botao()

    def _atualizar_estilo_botao(self):

        if self.bt_criar.isEnabled():
            self.bt_criar.setStyleSheet(f"""
                QPushButton {{
                    background:{tokens.SIDEBAR};
                    color:{tokens.TEXTO_CLARO};
                    font-weight:bold;
                    border-radius:10px;
                }}
                QPushButton:hover {{
                    background:{tokens.SIDEBAR_HOVER};
                }}
            """)
        else:
            self.bt_criar.setStyleSheet(f"""
                QPushButton {{
                    background:{tokens.BORDA_FORTE};
                    color:{tokens.TEXTO_CLARO};
                    font-weight:bold;
                    border-radius:10px;
                }}
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

        self.bt_criar.setEnabled(False)
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        rodar_em_thread(
            self,
            _criar_conta_e_logar,
            nome,
            email,
            senha,
            ao_sucesso=self._ao_criar_conta_sucesso,
            ao_erro=self._ao_criar_conta_erro,
            ao_finalizar=self._ao_criar_conta_finalizado,
        )

    def _ao_criar_conta_sucesso(self, resultado):

        response, pos_login = resultado

        if response.status_code != 200:

            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))
            return

        eh_primeiro_usuario, ok, _erro_login = pos_login

        if not ok:

            QMessageBox.critical(
                self,
                "Erro",
                "Conta criada, mas não foi possível entrar "
                "automaticamente. Tente acessar manualmente.",
            )
            return

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

    def _ao_criar_conta_erro(self, erro):

        if isinstance(erro, ConnectionError):
            QMessageBox.critical(
                self,
                "Servidor Offline",
                "Não foi possível conectar ao Backend.\n\n"
                "Verifique se o FastAPI está executando.",
            )
            return

        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_criar_conta_finalizado(self):
        self.bt_criar.setEnabled(True)
        QApplication.restoreOverrideCursor()

    def abrir_sistema(self):

        # me()+configuracoes() buscados aqui ANTES de construir
        # PrincipalWindow (que os aceita prontos, ver telas/principal.py)
        # em vez de deixar o __init__ dela buscar sincrono
        rodar_em_thread(
            self,
            _buscar_info_principal,
            ao_sucesso=self._ao_buscar_info_principal_sucesso,
            ao_erro=self._ao_buscar_info_principal_erro,
        )

    def _ao_buscar_info_principal_erro(self, erro):
        QMessageBox.critical(
            self,
            "Erro",
            f"Conta criada, mas não foi possível abrir o sistema.\n{erro}",
        )

    def _ao_buscar_info_principal_sucesso(self, resultado):

        from telas.principal import PrincipalWindow

        info_usuario, config = resultado

        self.principal = PrincipalWindow(info_usuario, config)
        self.principal.show()

    def ir_para_login(self):

        from telas.login import LoginWindow

        self.login = LoginWindow()
        self.login.show()
        self.close()
