from PySide6.QtCore import QEvent, Qt
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

from design import tokens
from design.animations import fade_in
from design.icons import icone, icone_pixmap
from design.widgets import BotaoPrimario, CampoTexto
from services.api import login
from telas.principal import PrincipalWindow


BENEFICIOS = [
    "Frente de caixa rápida, com atalhos de teclado",
    "Controle de estoque, clientes e fiado num só lugar",
    "Relatórios financeiros sempre atualizados",
]


class LoginWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Vertex ERP")
        self.resize(1040, 640)
        self.setMinimumSize(860, 560)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._construir_painel_marca(), stretch=5)
        layout.addWidget(self._construir_painel_formulario(), stretch=6)

        self.usuario.setFocus()

        fade_in(self, duracao=260)

    # ======================================
    # PAINEL ESQUERDO — MARCA
    # ======================================

    def _construir_painel_marca(self):

        painel = QFrame()
        painel.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 {tokens.PRIMARIA},
                    stop:1 #1E3A8A
                );
            }}
        """)

        layout = QVBoxLayout(painel)
        layout.setContentsMargins(56, 64, 56, 56)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignVCenter)

        marca = QLabel("V")
        marca.setFixedSize(56, 56)
        marca.setAlignment(Qt.AlignCenter)
        marca.setStyleSheet("""
            background: rgba(255, 255, 255, 0.16);
            color: white;
            border-radius: 16px;
            font-size: 26px;
            font-weight: 800;
        """)
        layout.addWidget(marca)
        layout.addSpacing(28)

        titulo = QLabel("Vertex ERP")
        titulo.setStyleSheet("""
            background:transparent; color:white;
            font-size:32px; font-weight:800;
        """)
        layout.addWidget(titulo)
        layout.addSpacing(10)

        descricao = QLabel(
            "A gestão completa da sua loja: vendas, estoque, clientes\n"
            "e financeiro, em um sistema só — rápido e sem complicação."
        )
        descricao.setWordWrap(True)
        descricao.setStyleSheet("""
            background:transparent; color: rgba(255, 255, 255, 0.82);
            font-size:14px; line-height: 1.5;
        """)
        layout.addWidget(descricao)
        layout.addSpacing(36)

        for texto in BENEFICIOS:
            layout.addWidget(self._linha_beneficio(texto))
            layout.addSpacing(16)

        layout.addStretch()

        return painel

    def _linha_beneficio(self, texto):

        linha = QWidget()
        linha.setStyleSheet("background:transparent;")

        linha_layout = QHBoxLayout(linha)
        linha_layout.setContentsMargins(0, 0, 0, 0)
        linha_layout.setSpacing(12)

        bolha = QLabel()
        bolha.setFixedSize(26, 26)
        bolha.setAlignment(Qt.AlignCenter)
        bolha.setStyleSheet("""
            background: rgba(255, 255, 255, 0.16);
            border-radius: 13px;
        """)
        bolha.setPixmap(icone_pixmap("check", cor="#FFFFFF", tamanho=14))

        lbl = QLabel(texto)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("""
            background:transparent; color: rgba(255, 255, 255, 0.92);
            font-size:13px; font-weight:500;
        """)

        linha_layout.addWidget(bolha)
        linha_layout.addWidget(lbl, stretch=1)

        return linha

    # ======================================
    # PAINEL DIREITO — FORMULÁRIO
    # ======================================

    def _construir_painel_formulario(self):

        painel = QFrame()
        painel.setStyleSheet(f"background:{tokens.CARD};")

        externo = QVBoxLayout(painel)
        externo.setAlignment(Qt.AlignCenter)

        miolo = QWidget()
        miolo.setFixedWidth(340)
        miolo.setStyleSheet("background:transparent;")

        layout = QVBoxLayout(miolo)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        titulo = QLabel("Acessar loja")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XXL}px; font-weight:800;
        """)

        subtitulo = QLabel("Entre com suas credenciais para continuar")
        subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_BASE}px;
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(32)

        lbl_email = QLabel("E-MAIL")
        lbl_email.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        self.usuario = CampoTexto("seu@contato.com")

        layout.addWidget(lbl_email)
        layout.addSpacing(6)
        layout.addWidget(self.usuario)
        layout.addSpacing(18)

        lbl_senha = QLabel("SENHA")
        lbl_senha.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        layout.addWidget(lbl_senha)
        layout.addSpacing(6)
        layout.addWidget(self._construir_campo_senha())
        layout.addSpacing(14)

        linha_opcoes = QHBoxLayout()

        self.manter_conectado = QCheckBox("Manter conectado")
        self.manter_conectado.setChecked(True)
        self.manter_conectado.setCursor(Qt.PointingHandCursor)
        self.manter_conectado.setStyleSheet(f"""
            QCheckBox {{
                background:transparent; color:{tokens.TEXTO_SECUNDARIO};
                font-size:{tokens.TAMANHO_SM}px;
            }}
            QCheckBox::indicator {{
                width: 16px; height: 16px;
                border-radius: 4px;
                border: 1.5px solid {tokens.BORDA_FORTE};
                background: {tokens.CARD};
            }}
            QCheckBox::indicator:checked {{
                border: 1.5px solid {tokens.PRIMARIA};
                background: {tokens.PRIMARIA};
            }}
        """)

        bt_esqueceu = QPushButton("Esqueceu a senha?")
        bt_esqueceu.setCursor(Qt.PointingHandCursor)
        bt_esqueceu.setAutoDefault(False)
        bt_esqueceu.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.PRIMARIA}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:600;
            }}
            QPushButton:hover {{ color:{tokens.PRIMARIA_HOVER}; }}
        """)
        bt_esqueceu.clicked.connect(self.esqueceu_senha)

        linha_opcoes.addWidget(self.manter_conectado)
        linha_opcoes.addStretch()
        linha_opcoes.addWidget(bt_esqueceu)

        layout.addLayout(linha_opcoes)
        layout.addSpacing(24)

        self.botao = BotaoPrimario("Entrar")
        self.botao.setMinimumHeight(46)
        self.botao.clicked.connect(self.entrar)

        layout.addWidget(self.botao)
        layout.addSpacing(20)

        rodape = QHBoxLayout()
        rodape.setAlignment(Qt.AlignCenter)
        rodape.setSpacing(4)

        lbl_rodape = QLabel("Precisa de uma nova conta?")
        lbl_rodape.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        bt_cadastrar = QPushButton("Cadastre-se")
        bt_cadastrar.setCursor(Qt.PointingHandCursor)
        bt_cadastrar.setAutoDefault(False)
        bt_cadastrar.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.PRIMARIA}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:700;
            }}
            QPushButton:hover {{ color:{tokens.PRIMARIA_HOVER}; }}
        """)
        bt_cadastrar.clicked.connect(self.ir_para_cadastro)

        rodape.addWidget(lbl_rodape)
        rodape.addWidget(bt_cadastrar)

        layout.addLayout(rodape)

        externo.addWidget(miolo)

        return painel

    def _construir_campo_senha(self):

        campo_senha = QFrame()
        self._estilizar_campo_senha(campo_senha, focado=False)
        campo_senha_layout = QHBoxLayout(campo_senha)
        campo_senha_layout.setContentsMargins(14, 0, 8, 0)
        campo_senha_layout.setSpacing(4)

        self.senha = QLineEdit()
        self.senha.setPlaceholderText("••••••••")
        self.senha.setMinimumHeight(44)
        self.senha.setEchoMode(QLineEdit.Password)
        self.senha.setStyleSheet(f"""
            QLineEdit {{
                background:transparent; border:none;
                font-size:{tokens.TAMANHO_MD}px; color:{tokens.TEXTO};
            }}
        """)
        self.senha.returnPressed.connect(self.entrar)
        self.senha.installEventFilter(self)
        self._campo_senha_frame = campo_senha

        self.bt_ver_senha = QPushButton()
        self.bt_ver_senha.setFixedSize(30, 30)
        self.bt_ver_senha.setCursor(Qt.PointingHandCursor)
        self.bt_ver_senha.setAutoDefault(False)
        self.bt_ver_senha.setCheckable(True)
        self.bt_ver_senha.setIcon(icone("eye", cor=tokens.TEXTO_TERCIARIO, tamanho=18))
        self.bt_ver_senha.setStyleSheet("""
            QPushButton { background:transparent; border:none; }
        """)
        self.bt_ver_senha.clicked.connect(self.alternar_ver_senha)

        campo_senha_layout.addWidget(self.senha)
        campo_senha_layout.addWidget(self.bt_ver_senha)

        return campo_senha

    def _estilizar_campo_senha(self, campo_senha, focado):

        cor_borda = tokens.PRIMARIA if focado else tokens.BORDA

        campo_senha.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border: 1.5px solid {cor_borda};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

    def eventFilter(self, observado, evento):

        if observado is self.senha:
            if evento.type() == QEvent.FocusIn:
                self._estilizar_campo_senha(self._campo_senha_frame, focado=True)
            elif evento.type() == QEvent.FocusOut:
                self._estilizar_campo_senha(self._campo_senha_frame, focado=False)

        return super().eventFilter(observado, evento)

    # ======================================
    # COMPORTAMENTO
    # ======================================

    def ir_para_cadastro(self):

        from telas.cadastro_inicial import CadastroInicialWindow

        self.cadastro = CadastroInicialWindow()
        self.cadastro.show()
        self.close()

    def alternar_ver_senha(self):

        if self.bt_ver_senha.isChecked():
            self.senha.setEchoMode(QLineEdit.Normal)
            self.bt_ver_senha.setIcon(
                icone("eye-off", cor=tokens.TEXTO_TERCIARIO, tamanho=18)
            )
        else:
            self.senha.setEchoMode(QLineEdit.Password)
            self.bt_ver_senha.setIcon(
                icone("eye", cor=tokens.TEXTO_TERCIARIO, tamanho=18)
            )

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
