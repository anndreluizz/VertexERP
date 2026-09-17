from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from utils.validacao import email_valido
from services.user_service import (
    listar_usuarios,
    atualizar_usuario,
    criar_usuario,
    redefinir_senha,
)
from services.worker import rodar_em_thread

from design import tokens
from design.responsive import tamanho_fixo_seguro
from design.widgets import BotaoPerigo, BotaoPrimario, BotaoSecundario, BotaoSucesso
from widgets.fields.email_field import EmailField


class NovoUsuarioDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Novo Usuário")
        tamanho_fixo_seguro(self, 400, 420)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        titulo = QLabel("Novo Usuário")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            "Crie o acesso de um novo funcionário ao sistema."
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(10)

        self.nome = self._campo(layout, "NOME COMPLETO", "Nome")
        self.email = self._campo(
            layout, "E-MAIL", "email@exemplo.com", cls=EmailField
        )
        self.senha = self._campo(
            layout, "SENHA", "••••••", senha=True
        )
        self.confirmar = self._campo(
            layout, "CONFIRMAR SENHA", "••••••", senha=True
        )

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.setMinimumHeight(44)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.clicked.connect(self.reject)

        self.bt_criar = BotaoSucesso("Cadastrar")
        self.bt_criar.setMinimumHeight(44)
        self.bt_criar.setAutoDefault(False)
        self.bt_criar.clicked.connect(self.criar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(self.bt_criar)

        layout.addLayout(botoes)

        self.nome.setFocus()

    def _campo(self, layout, rotulo, placeholder, senha=False, cls=None):

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        if cls is None:
            campo = QLineEdit()
            campo.setPlaceholderText(placeholder)
            campo.setMinimumHeight(40)
            campo.setStyleSheet(f"""
                QLineEdit {{
                    border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                    padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                    background: {tokens.CARD};
                }}
                QLineEdit:focus {{ border: 1.5px solid {tokens.PRIMARIA}; }}
            """)

            if senha:
                campo.setEchoMode(QLineEdit.Password)
        else:
            # cls (ex.: EmailField) já traz sua própria máscara/validação
            # e estilo (baseado em CampoTexto) -- não sobrescrever.
            campo = cls(placeholder)

        layout.addWidget(lbl)
        layout.addWidget(campo)

        return campo

    def criar(self):

        nome = self.nome.text().strip()
        email = self.email.text().strip()
        senha = self.senha.text()

        if not nome or not email or not senha:
            QMessageBox.warning(
                self, "Atenção", "Preencha todos os campos."
            )
            return

        if not email_valido(email):
            QMessageBox.warning(
                self, "Atenção", "Informe um e-mail válido (ex.: nome@exemplo.com)."
            )
            return

        if senha != self.confirmar.text():
            QMessageBox.warning(
                self, "Atenção", "As senhas não coincidem."
            )
            return

        self.bt_criar.setEnabled(False)

        rodar_em_thread(
            self,
            criar_usuario,
            nome,
            email,
            senha,
            ao_sucesso=self._ao_criar_sucesso,
            ao_erro=self._ao_criar_erro,
            ao_finalizar=self._ao_criar_finalizado,
        )

    def _ao_criar_sucesso(self, response):

        if response.status_code == 200:
            self.accept()
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_criar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_criar_finalizado(self):
        self.bt_criar.setEnabled(True)


class RedefinirSenhaDialog(QDialog):
    """Admin redefinindo a senha de outro usuário (ex.: funcionário
    esqueceu a senha) -- ao contrário de TrocarSenhaDialog (self
    service, em telas/trocar_senha.py), aqui não precisa saber a
    senha antiga: quem autoriza é o admin logado."""

    def __init__(self, nome_usuario, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Redefinir Senha")
        tamanho_fixo_seguro(self, 400, 320)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)

        titulo = QLabel("Redefinir Senha")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(f"Defina uma nova senha para {nome_usuario}.")
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(10)

        self.senha_nova = self._campo(layout, "NOVA SENHA")
        self.confirmar = self._campo(layout, "CONFIRMAR NOVA SENHA")

        layout.addStretch()

        botoes = QHBoxLayout()
        botoes.setSpacing(10)

        bt_cancelar = BotaoSecundario("Cancelar")
        bt_cancelar.setMinimumHeight(44)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.clicked.connect(self.reject)

        bt_salvar = BotaoSucesso("Salvar")
        bt_salvar.setMinimumHeight(44)
        bt_salvar.setAutoDefault(False)
        bt_salvar.clicked.connect(self.salvar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(bt_salvar)

        layout.addLayout(botoes)

        self.senha_nova.setFocus()

    def _campo(self, layout, rotulo):

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            font-weight:700; color:{tokens.TEXTO_TERCIARIO};
        """)

        campo = QLineEdit()
        campo.setPlaceholderText("••••••")
        campo.setEchoMode(QLineEdit.Password)
        campo.setMinimumHeight(40)
        campo.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QLineEdit:focus {{ border: 1.5px solid {tokens.PRIMARIA}; }}
        """)

        layout.addWidget(lbl)
        layout.addWidget(campo)

        return campo

    def salvar(self):

        senha_nova = self.senha_nova.text()
        confirmar = self.confirmar.text()

        if not senha_nova:
            QMessageBox.warning(
                self, "Atenção", "Informe a nova senha."
            )
            return

        if senha_nova != confirmar:
            QMessageBox.warning(
                self, "Atenção", "A nova senha e a confirmação não coincidem."
            )
            return

        self.senha_nova_confirmada = senha_nova
        self.accept()


class GerenciarUsuariosDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.usuarios = []
        self._carregando = False

        self.setWindowTitle("Gerenciar Usuários")
        self.resize(680, 500)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        cabecalho = QHBoxLayout()

        titulo = QLabel("Gerenciar Usuários")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        bt_novo = BotaoSucesso("Novo Usuário", icone_nome="plus")
        bt_novo.setAutoDefault(False)
        bt_novo.clicked.connect(self.novo_usuario)

        cabecalho.addWidget(titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(bt_novo)

        layout.addLayout(cabecalho)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(5)
        self.tabela.setHorizontalHeaderLabels(
            ["Nome", "E-mail", "Status", "Admin", "2FA"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela.verticalHeader().setDefaultSectionSize(40)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SingleSelection)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setShowGrid(False)
        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                alternate-background-color: {tokens.FUNDO};
                font-size: {tokens.TAMANHO_BASE}px;
            }}
            QTableWidget::item:selected {{
                background: {tokens.PRIMARIA};
                color: white;
            }}
            QHeaderView::section {{
                background: {tokens.FUNDO};
                color: {tokens.TEXTO_SECUNDARIO};
                font-weight: 700;
                font-size: {tokens.TAMANHO_XS}px;
                padding: 8px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
        """)

        layout.addWidget(self.tabela, stretch=1)

        rodape = QHBoxLayout()
        rodape.setSpacing(10)

        self.bt_ativar_desativar = BotaoPerigo("Ativar / Desativar")
        self.bt_ativar_desativar.setAutoDefault(False)
        self.bt_ativar_desativar.clicked.connect(
            self.alternar_ativo
        )

        self.bt_admin = BotaoPrimario("Tornar / Remover Admin")
        self.bt_admin.setAutoDefault(False)
        self.bt_admin.clicked.connect(self.alternar_admin)

        self.bt_redefinir_senha = BotaoSecundario("Redefinir Senha")
        self.bt_redefinir_senha.setAutoDefault(False)
        self.bt_redefinir_senha.clicked.connect(self.redefinir_senha_usuario)

        self.bt_2fa = BotaoSecundario("Ativar / Desativar 2FA")
        self.bt_2fa.setAutoDefault(False)
        self.bt_2fa.clicked.connect(self.alternar_2fa)

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.setAutoDefault(False)
        bt_fechar.clicked.connect(self.accept)

        rodape.addWidget(self.bt_ativar_desativar)
        rodape.addWidget(self.bt_admin)
        rodape.addWidget(self.bt_redefinir_senha)
        rodape.addWidget(self.bt_2fa)
        rodape.addStretch()
        rodape.addWidget(bt_fechar)

        layout.addLayout(rodape)

        self.carregar()

    # ======================================

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            listar_usuarios,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_ativar_desativar.setEnabled(not carregando)
        self.bt_admin.setEnabled(not carregando)
        self.bt_redefinir_senha.setEnabled(not carregando)
        self.bt_2fa.setEnabled(not carregando)

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar os usuários.\n{erro}")

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    def _ao_carregar_sucesso(self, usuarios):

        self.usuarios = usuarios

        self.tabela.setRowCount(len(self.usuarios))

        for linha, usuario in enumerate(self.usuarios):

            self.tabela.setItem(
                linha, 0, QTableWidgetItem(usuario.get("nome") or "")
            )
            self.tabela.setItem(
                linha, 1, QTableWidgetItem(usuario.get("email") or "")
            )

            ativo = usuario.get("ativo", True)
            item_status = QTableWidgetItem("Ativo" if ativo else "Inativo")
            item_status.setForeground(
                QColor(tokens.SECUNDARIA_HOVER if ativo else tokens.ERRO)
            )
            self.tabela.setItem(linha, 2, item_status)

            admin = usuario.get("admin")
            item_admin = QTableWidgetItem("Sim" if admin else "Não")
            item_admin.setForeground(
                QColor(tokens.PRIMARIA if admin else tokens.TEXTO_TERCIARIO)
            )
            self.tabela.setItem(linha, 3, item_admin)

            dois_fatores = usuario.get("dois_fatores_ativo")
            item_2fa = QTableWidgetItem("Ativo" if dois_fatores else "Desativado")
            item_2fa.setForeground(
                QColor(tokens.SECUNDARIA_HOVER if dois_fatores else tokens.TEXTO_TERCIARIO)
            )
            self.tabela.setItem(linha, 4, item_2fa)

        self.tabela.setCurrentCell(-1, -1)
        self.tabela.clearSelection()

    def _usuario_selecionado(self):

        linha = self.tabela.currentRow()

        if linha < 0:
            QMessageBox.warning(
                self, "Aviso", "Selecione um usuário."
            )
            return None

        return self.usuarios[linha]

    def novo_usuario(self):

        dialogo = NovoUsuarioDialog(parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        self.carregar()

    def alternar_ativo(self):

        usuario = self._usuario_selecionado()

        if usuario is None:
            return

        novo_status = not usuario.get("ativo", True)

        resposta = QMessageBox.question(
            self,
            "Confirmar",
            (
                f"Desativar o acesso de {usuario['nome']}?"
                if not novo_status
                else f"Reativar o acesso de {usuario['nome']}?"
            ),
        )

        if resposta != QMessageBox.Yes:
            return

        self._atualizar_usuario_async(usuario["id"], {"ativo": novo_status})

    def _atualizar_usuario_async(self, usuario_id, campos):

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            atualizar_usuario,
            usuario_id,
            campos,
            ao_sucesso=self._ao_atualizar_usuario_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_atualizar_usuario_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutacao_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutacao_finalizada(self):
        if not self._carregando:
            self._definir_controles_carregando(False)

    def alternar_admin(self):

        usuario = self._usuario_selecionado()

        if usuario is None:
            return

        novo_admin = not usuario.get("admin", False)

        resposta = QMessageBox.question(
            self,
            "Confirmar",
            (
                f"Tornar {usuario['nome']} administrador?"
                if novo_admin
                else f"Remover {usuario['nome']} da administração?"
            ),
        )

        if resposta != QMessageBox.Yes:
            return

        self._atualizar_usuario_async(usuario["id"], {"admin": novo_admin})

    def alternar_2fa(self):

        usuario = self._usuario_selecionado()

        if usuario is None:
            return

        novo_valor = not usuario.get("dois_fatores_ativo", False)

        resposta = QMessageBox.question(
            self,
            "Confirmar",
            (
                f"Ativar a verificação em duas etapas (2FA) pra "
                f"{usuario['nome']}? Um código será enviado por "
                "e-mail em todo login a partir de agora."
                if novo_valor
                else f"Desativar a verificação em duas etapas (2FA) "
                f"de {usuario['nome']}?"
            ),
        )

        if resposta != QMessageBox.Yes:
            return

        self._atualizar_usuario_async(
            usuario["id"], {"dois_fatores_ativo": novo_valor}
        )

    def redefinir_senha_usuario(self):

        usuario = self._usuario_selecionado()

        if usuario is None:
            return

        dialogo = RedefinirSenhaDialog(usuario["nome"], parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        self._redefinir_senha_usuario_nome = usuario["nome"]
        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            redefinir_senha,
            usuario["id"],
            dialogo.senha_nova_confirmada,
            ao_sucesso=self._ao_redefinir_senha_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_redefinir_senha_sucesso(self, response):

        if response.status_code == 200:
            QMessageBox.information(
                self, "Sucesso",
                f"Senha de {self._redefinir_senha_usuario_nome} redefinida."
            )
        else:
            try:
                erro = response.json().get("detail") or str(
                    response.json()
                )
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))
