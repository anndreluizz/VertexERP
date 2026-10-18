from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils.validacao import email_valido
from services.user_service import (
    listar_usuarios,
    atualizar_usuario,
    criar_usuario,
    redefinir_senha,
)
from services.perfil_service import listar_perfis
from services.loja_service import listar_lojas
from services import api
from services.worker import rodar_em_thread, em_paralelo
from telas.gerenciar_perfis import GerenciarPerfisDialog
from telas.log_auditoria import LogAuditoriaDialog

from design import tokens
from design.icons import icone
from design.widgets import (
    Avatar, Badge, BotaoPerigo, BotaoPrimario, BotaoSecundario, BotaoSucesso,
    CampoTexto, DialogoPadrao, campo_rotulado, grade_formulario, tabela_lista,
    titulo_secao,
)
from widgets.fields.email_field import EmailField

# o backend aceita qualquer senha não vazia; aqui pede o mínimo pra não
# nascer acesso com senha "1" ou "123"
SENHA_MINIMA = 6


# ======================================
# PEÇAS DE SENHA
# ======================================

def _forca_senha(senha):
    """(texto, cor, nível 0-4) da força da senha, pro medidor ao vivo."""

    if not senha:
        return "", tokens.TEXTO_TERCIARIO, 0
    if len(senha) < SENHA_MINIMA:
        return f"Muito curta (mínimo {SENHA_MINIMA} caracteres)", tokens.ERRO, 1

    pontos = sum((
        len(senha) >= 8,
        any(c.isdigit() for c in senha),
        any(c.isupper() for c in senha) and any(c.islower() for c in senha),
        any(not c.isalnum() for c in senha),
    ))
    if pontos <= 1:
        return "Fraca · misture letras, números e símbolos", tokens.ALERTA, 2
    if pontos <= 2:
        return "Razoável", tokens.ALERTA, 3
    return "Forte", tokens.SECUNDARIA_HOVER, 4


def campo_senha(placeholder="Mínimo 6 caracteres"):
    """CampoTexto de senha com o olho de mostrar/esconder dentro."""

    campo = CampoTexto(placeholder)
    campo.setEchoMode(QLineEdit.Password)

    acao = campo.addAction(
        icone("eye", cor=tokens.TEXTO_TERCIARIO, tamanho=16), QLineEdit.TrailingPosition
    )
    acao.setToolTip("Mostrar senha")

    def alternar():
        mostrando = campo.echoMode() == QLineEdit.Normal
        campo.setEchoMode(QLineEdit.Password if mostrando else QLineEdit.Normal)
        acao.setIcon(icone("eye" if mostrando else "eye-off", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        acao.setToolTip("Mostrar senha" if mostrando else "Esconder senha")

    acao.triggered.connect(alternar)
    return campo


class _PainelSenha:
    """Senha + confirmação com medidor de força e aviso de "não confere"
    ao vivo -- o erro aparece enquanto digita, não só ao salvar."""

    def __init__(self, rotulo_senha, rotulo_confirmar):

        self.senha = campo_senha()
        self.confirmar = campo_senha("Digite a senha de novo")

        self.barras = []
        linha_barras = QHBoxLayout()
        linha_barras.setSpacing(4)
        for _ in range(4):
            barra = QFrame()
            barra.setFixedHeight(4)
            linha_barras.addWidget(barra, 1)
            self.barras.append(barra)

        self.lbl_forca = QLabel()
        self.lbl_confere = QLabel()

        bloco_senha = QWidget()
        bloco_senha.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(bloco_senha)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(campo_rotulado(rotulo_senha, self.senha))
        layout.addLayout(linha_barras)
        layout.addWidget(self.lbl_forca)

        bloco_confirmar = QWidget()
        bloco_confirmar.setStyleSheet("background:transparent;")
        layout = QVBoxLayout(bloco_confirmar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(campo_rotulado(rotulo_confirmar, self.confirmar))
        layout.addWidget(self.lbl_confere)
        layout.addStretch()

        self.bloco_senha, self.bloco_confirmar = bloco_senha, bloco_confirmar

        self.senha.textChanged.connect(self._atualizar)
        self.confirmar.textChanged.connect(self._atualizar)
        self._atualizar()

    @staticmethod
    def _pintar(lbl, cor):
        lbl.setStyleSheet(
            f"background:transparent; font-size:{tokens.TAMANHO_XS}px; "
            f"color:{cor}; font-weight:600;"
        )

    def _atualizar(self):

        texto, cor, nivel = _forca_senha(self.senha.text())
        for indice, barra in enumerate(self.barras):
            barra.setStyleSheet(
                f"background:{cor if indice < nivel else tokens.BORDA}; border-radius:2px;"
            )
        self.lbl_forca.setText(texto)
        self._pintar(self.lbl_forca, cor)

        confirmar = self.confirmar.text()
        if not confirmar:
            self.lbl_confere.setText("")
        elif confirmar == self.senha.text():
            self.lbl_confere.setText("✓ As senhas conferem")
            self._pintar(self.lbl_confere, tokens.SECUNDARIA_HOVER)
        else:
            self.lbl_confere.setText("As senhas não conferem")
            self._pintar(self.lbl_confere, tokens.ERRO)

    def erro(self):
        """Mensagem do que impede salvar, ou None."""
        senha = self.senha.text()
        if not senha:
            return "Informe a senha."
        if len(senha) < SENHA_MINIMA:
            return f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres."
        if senha != self.confirmar.text():
            return "A senha e a confirmação não conferem."
        return None


def _estilo_combo():
    return f"""
        QComboBox {{
            border:1.5px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
            padding:0 14px; min-height:42px; font-size:{tokens.TAMANHO_MD}px;
            color:{tokens.TEXTO}; background:{tokens.CARD};
        }}
        QComboBox:focus {{ border-color:{tokens.PRIMARIA}; }}
        QComboBox:disabled {{ background:{tokens.FUNDO}; color:{tokens.TEXTO_TERCIARIO}; }}
        QComboBox QAbstractItemView {{
            background:{tokens.CARD}; color:{tokens.TEXTO};
            selection-background-color:{tokens.PRIMARIA_CLARA};
            selection-color:{tokens.PRIMARIA};
        }}
    """


def _erro_resposta(response):
    try:
        return response.json().get("detail") or str(response.json())
    except Exception:
        return response.text


def _criar_com_perfil(nome, email, senha, perfil_id):
    """Roda na worker thread -- cria o usuário e, se escolheu perfil,
    já atribui (o POST /users/ não recebe perfil)."""

    response = criar_usuario(nome, email, senha)
    if response.status_code == 200 and perfil_id is not None:
        usuario_id = response.json().get("data", {}).get("id")
        if usuario_id:
            atualizar_usuario(usuario_id, {"perfil_id": perfil_id})
    return response


# ======================================
# NOVO USUÁRIO
# ======================================

class NovoUsuarioDialog(DialogoPadrao):

    def __init__(self, perfis=None, parent=None):

        super().__init__(
            "Novo usuário", "Crie o acesso de um funcionário ao sistema",
            "user", tokens.SECUNDARIA, tokens.SUCESSO_CLARO,
            largura=DialogoPadrao.MEDIO, parent=parent,
        )

        self.nome = CampoTexto("Ex.: Maria da Silva")
        self.email = EmailField("email@exemplo.com")
        self.painel_senha = _PainelSenha("Senha", "Confirmar senha")
        self.senha = self.painel_senha.senha
        self.confirmar = self.painel_senha.confirmar

        self.perfil = QComboBox()
        self.perfil.setStyleSheet(_estilo_combo())
        self.perfil.addItem("Vendedor (só as próprias vendas e caixa)", None)
        for perfil in perfis or []:
            self.perfil.addItem(perfil["nome"], perfil["id"])

        self.corpo.addWidget(titulo_secao("Dados do funcionário"))
        self.corpo.addLayout(grade_formulario(
            (campo_rotulado("Nome completo", self.nome), 0, 0),
            (campo_rotulado("E-mail (é o login)", self.email), 0, 1),
        ))

        self.corpo.addWidget(titulo_secao("Senha de acesso"))
        self.corpo.addLayout(grade_formulario(
            (self.painel_senha.bloco_senha, 0, 0),
            (self.painel_senha.bloco_confirmar, 0, 1),
        ))

        self.corpo.addWidget(titulo_secao("Permissões"))
        self.corpo.addLayout(grade_formulario(
            (campo_rotulado(
                "Perfil de acesso", self.perfil,
                "Define o que o funcionário pode fazer. Dá pra trocar depois.",
            ), 0, 0),
        ))
        self.corpo.addStretch()

        self.bt_criar = BotaoSucesso("Cadastrar usuário", icone_nome="check")
        self.bt_criar.setAutoDefault(False)
        self.bt_criar.clicked.connect(self.criar)
        self.definir_botoes(self.bt_criar)

        # Enter vai pro próximo campo; no último, cadastra
        self.nome.returnPressed.connect(self.email.setFocus)
        self.email.returnPressed.connect(self.senha.setFocus)
        self.senha.returnPressed.connect(self.confirmar.setFocus)
        self.confirmar.returnPressed.connect(self.criar)

        self.ajustar_altura()
        self.nome.setFocus()

    def criar(self):

        nome = self.nome.text().strip()
        email = self.email.text().strip()

        if not nome:
            QMessageBox.warning(self, "Atenção", "Informe o nome do funcionário.")
            self.nome.setFocus()
            return

        if not email_valido(email):
            QMessageBox.warning(
                self, "Atenção", "Informe um e-mail válido (ex.: nome@exemplo.com)."
            )
            self.email.setFocus()
            return

        erro = self.painel_senha.erro()
        if erro:
            QMessageBox.warning(self, "Atenção", erro)
            self.senha.setFocus()
            return

        self.bt_criar.setEnabled(False)

        rodar_em_thread(
            self,
            _criar_com_perfil,
            nome,
            email,
            self.senha.text(),
            self.perfil.currentData(),
            ao_sucesso=self._ao_criar_sucesso,
            ao_erro=self._ao_criar_erro,
            ao_finalizar=self._ao_criar_finalizado,
        )

    def _ao_criar_sucesso(self, response):

        if response.status_code == 200:
            self.accept()
        else:
            QMessageBox.critical(self, "Erro", str(_erro_resposta(response)))

    def _ao_criar_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_criar_finalizado(self):
        self.bt_criar.setEnabled(True)


# ======================================
# REDEFINIR SENHA
# ======================================

class RedefinirSenhaDialog(DialogoPadrao):
    """Admin redefinindo a senha de outro usuário (ex.: funcionário
    esqueceu a senha) -- ao contrário de TrocarSenhaDialog (self
    service, em telas/trocar_senha.py), aqui não precisa saber a
    senha antiga: quem autoriza é o admin logado."""

    def __init__(self, nome_usuario, parent=None):

        super().__init__(
            "Redefinir senha", f"Nova senha para {nome_usuario}",
            "lock", tokens.ALERTA, tokens.ALERTA_CLARO,
            largura=DialogoPadrao.PEQUENO, parent=parent,
        )

        self.painel_senha = _PainelSenha("Nova senha", "Confirmar nova senha")
        self.senha_nova = self.painel_senha.senha
        self.confirmar = self.painel_senha.confirmar

        aviso = QLabel(
            "O funcionário será desconectado dos outros computadores e "
            "vai precisar entrar de novo com a senha nova."
        )
        aviso.setWordWrap(True)
        aviso.setStyleSheet(f"""
            background:{tokens.ALERTA_CLARO}; color:{tokens.ALERTA_TEXTO};
            font-size:{tokens.TAMANHO_SM}px; border-radius:{tokens.RADIUS_SM}px;
            border-left:4px solid {tokens.ALERTA}; padding:10px 12px;
        """)

        self.corpo.addWidget(aviso)
        self.corpo.addWidget(self.painel_senha.bloco_senha)
        self.corpo.addWidget(self.painel_senha.bloco_confirmar)
        self.corpo.addStretch()

        bt_salvar = BotaoSucesso("Salvar nova senha", icone_nome="check")
        bt_salvar.setAutoDefault(False)
        bt_salvar.clicked.connect(self.salvar)
        self.definir_botoes(bt_salvar)

        self.senha_nova.returnPressed.connect(self.confirmar.setFocus)
        self.confirmar.returnPressed.connect(self.salvar)

        self.ajustar_altura()
        self.senha_nova.setFocus()

    def salvar(self):

        erro = self.painel_senha.erro()
        if erro:
            QMessageBox.warning(self, "Atenção", erro)
            self.senha_nova.setFocus()
            return

        self.senha_nova_confirmada = self.senha_nova.text()
        self.accept()


# ======================================
# LISTA DE USUÁRIOS + PAINEL DO SELECIONADO
# ======================================

class GerenciarUsuariosDialog(DialogoPadrao):

    def __init__(self, parent=None):

        super().__init__(
            "Usuários", "Quem acessa o sistema e o que cada um pode fazer",
            "users", largura=DialogoPadrao.GRANDE, parent=parent,
        )
        self.resize(DialogoPadrao.GRANDE, 700)

        self.usuarios = []
        self.perfis = []
        self.lojas = []
        self.meu_id = None
        self._carregando = False
        self._selecionar_id = None

        # ---- barra: busca + novo ----
        barra = QHBoxLayout()
        barra.setSpacing(10)

        self.busca = CampoTexto("Buscar por nome ou e-mail...")
        self.busca.addAction(
            icone("search", cor=tokens.TEXTO_TERCIARIO, tamanho=16), QLineEdit.LeadingPosition
        )
        self.busca.textChanged.connect(self._filtrar)

        bt_novo = BotaoSucesso("Novo usuário", icone_nome="plus")
        bt_novo.setAutoDefault(False)
        bt_novo.setMinimumHeight(44)
        bt_novo.clicked.connect(self.novo_usuario)

        barra.addWidget(self.busca, 1)
        barra.addWidget(bt_novo)
        self.corpo.addLayout(barra)

        # ---- lista | painel ----
        self.tabela = tabela_lista(["Nome", "Perfil", "Situação"])
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.Stretch)
        cabecalho.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        cabecalho.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tabela.verticalHeader().setDefaultSectionSize(52)
        self.tabela.itemSelectionChanged.connect(self._mostrar_selecionado)

        self.painel = QFrame()
        self.painel.setObjectName("painelUsuario")
        self.painel.setStyleSheet(f"""
            QFrame#painelUsuario {{
                background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_MD}px;
            }}
        """)
        self.painel.setMinimumWidth(330)
        self.painel_layout = QVBoxLayout(self.painel)
        self.painel_layout.setContentsMargins(20, 20, 20, 20)
        self.painel_layout.setSpacing(12)
        self._montar_painel()

        colunas = QHBoxLayout()
        colunas.setSpacing(16)
        colunas.addWidget(self.tabela, 3)
        colunas.addWidget(self.painel, 2)
        self.corpo.addLayout(colunas, 1)

        # ---- rodapé ----
        bt_gerenciar_perfis = BotaoSecundario("Perfis de acesso", icone_nome="lock")
        bt_gerenciar_perfis.setAutoDefault(False)
        bt_gerenciar_perfis.clicked.connect(self.gerenciar_perfis)

        bt_auditoria = BotaoSecundario("Auditoria", icone_nome="file-text")
        bt_auditoria.setAutoDefault(False)
        bt_auditoria.clicked.connect(self.ver_auditoria)

        bt_fechar = BotaoPrimario("Fechar")
        bt_fechar.setAutoDefault(False)
        bt_fechar.setMinimumWidth(140)
        bt_fechar.clicked.connect(self.accept)

        self.rodape.addWidget(bt_gerenciar_perfis)
        self.rodape.addWidget(bt_auditoria)
        self.rodape.addStretch()
        self.rodape.addWidget(bt_fechar)

        for tecla, acao in (("Ctrl+N", self.novo_usuario), ("Ctrl+F", self.busca.setFocus)):
            atalho = QShortcut(QKeySequence(tecla), self)
            atalho.activated.connect(acao)

        self.carregar()

    # ======================================
    # PAINEL DO USUÁRIO SELECIONADO
    # ======================================

    def _rotulo_painel(self, texto):
        lbl = QLabel(texto.upper())
        lbl.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px; font-weight:800;
            color:{tokens.TEXTO_SECUNDARIO}; letter-spacing:0.5px;
        """)
        return lbl

    @staticmethod
    def _esvaziar(layout):
        while layout.count():
            widget = layout.takeAt(0).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    def _montar_painel(self):

        # vazio (nada selecionado)
        self.painel_vazio = QLabel("Selecione um usuário na lista\npra ver e alterar o acesso.")
        self.painel_vazio.setAlignment(Qt.AlignCenter)
        self.painel_vazio.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_BASE}px;
        """)
        self.painel_layout.addWidget(self.painel_vazio, 1)

        self.painel_conteudo = QWidget()
        self.painel_conteudo.setStyleSheet("background:transparent;")
        conteudo = QVBoxLayout(self.painel_conteudo)
        conteudo.setContentsMargins(0, 0, 0, 0)
        conteudo.setSpacing(12)

        # identificação
        linha_id = QHBoxLayout()
        linha_id.setSpacing(12)
        self.avatar_slot = QHBoxLayout()
        linha_id.addLayout(self.avatar_slot)
        col_nome = QVBoxLayout()
        col_nome.setSpacing(2)
        self.lbl_nome = QLabel()
        self.lbl_nome.setWordWrap(True)
        self.lbl_nome.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        self.lbl_email = QLabel()
        self.lbl_email.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px; color:{tokens.TEXTO_SECUNDARIO};
        """)
        col_nome.addWidget(self.lbl_nome)
        col_nome.addWidget(self.lbl_email)
        linha_id.addLayout(col_nome, 1)
        conteudo.addLayout(linha_id)

        self.linha_badges = QHBoxLayout()
        self.linha_badges.setSpacing(6)
        conteudo.addLayout(self.linha_badges)

        # perfil (troca na hora, sem caixinha extra)
        conteudo.addWidget(self._rotulo_painel("Perfil de acesso"))
        self.combo_perfil = QComboBox()
        self.combo_perfil.setStyleSheet(_estilo_combo())
        self.combo_perfil.activated.connect(self._ao_escolher_perfil)
        conteudo.addWidget(self.combo_perfil)

        # loja: preso a ela, so' ve e registra nela (ver resolver_loja_id)
        self.lbl_loja = self._rotulo_painel("Loja")
        conteudo.addWidget(self.lbl_loja)
        self.combo_loja = QComboBox()
        self.combo_loja.setStyleSheet(_estilo_combo())
        self.combo_loja.activated.connect(self._ao_escolher_loja)
        conteudo.addWidget(self.combo_loja)

        # segurança
        conteudo.addWidget(self._rotulo_painel("Segurança"))
        grade = QGridLayout()
        grade.setSpacing(8)
        self.bt_redefinir_senha = BotaoSecundario("Redefinir senha", icone_nome="lock")
        self.bt_redefinir_senha.setAutoDefault(False)
        self.bt_redefinir_senha.clicked.connect(self.redefinir_senha_usuario)
        self.bt_2fa = BotaoSecundario("Ativar 2FA", icone_nome="mail")
        self.bt_2fa.setAutoDefault(False)
        self.bt_2fa.setToolTip("Verificação em duas etapas: código por e-mail a cada login")
        self.bt_2fa.clicked.connect(self.alternar_2fa)
        grade.addWidget(self.bt_redefinir_senha, 0, 0)
        grade.addWidget(self.bt_2fa, 0, 1)
        conteudo.addLayout(grade)

        # acesso
        conteudo.addWidget(self._rotulo_painel("Acesso"))
        self.slot_acesso = QGridLayout()
        self.slot_acesso.setSpacing(8)
        conteudo.addLayout(self.slot_acesso)
        self.bt_admin = None
        self.bt_ativar_desativar = None

        self.lbl_aviso_proprio = QLabel("Este é você: não dá pra desativar a própria conta.")
        self.lbl_aviso_proprio.setWordWrap(True)
        self.lbl_aviso_proprio.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px; color:{tokens.TEXTO_TERCIARIO};
        """)
        conteudo.addWidget(self.lbl_aviso_proprio)

        conteudo.addStretch()
        self.painel_layout.addWidget(self.painel_conteudo, 1)
        self.painel_conteudo.hide()

    def _botoes_acesso(self, usuario):
        """Botões com o texto exato do que vão fazer ("Desativar acesso"
        ou "Reativar acesso"), em vez de "Ativar / Desativar"."""

        self._esvaziar(self.slot_acesso)

        admin = usuario.get("admin", False)
        ativo = usuario.get("ativo", True)
        proprio = usuario.get("id") == self.meu_id

        if admin:
            self.bt_admin = BotaoSecundario("Tirar admin", icone_nome="user")
        else:
            self.bt_admin = BotaoPrimario("Tornar admin", icone_nome="star")
        self.bt_admin.setAutoDefault(False)
        self.bt_admin.clicked.connect(self.alternar_admin)

        if ativo:
            self.bt_ativar_desativar = BotaoPerigo("Desativar", icone_nome="x")
        else:
            self.bt_ativar_desativar = BotaoSucesso("Reativar", icone_nome="check")
        self.bt_ativar_desativar.setAutoDefault(False)
        self.bt_ativar_desativar.clicked.connect(self.alternar_ativo)
        self.bt_ativar_desativar.setEnabled(not (proprio and ativo))

        self.slot_acesso.addWidget(self.bt_admin, 0, 0)
        self.slot_acesso.addWidget(self.bt_ativar_desativar, 0, 1)
        self.lbl_aviso_proprio.setVisible(proprio)

    def _mostrar_selecionado(self):

        usuario = self._usuario_atual()
        if usuario is None:
            self.painel_conteudo.hide()
            self.painel_vazio.show()
            return

        self._esvaziar(self.avatar_slot)
        self.avatar_slot.addWidget(Avatar(usuario.get("nome") or "?", 52))

        self.lbl_nome.setText(usuario.get("nome") or "")
        self.lbl_email.setText(usuario.get("email") or "")

        while self.linha_badges.count():
            item = self.linha_badges.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
                item.widget().deleteLater()
        ativo = usuario.get("ativo", True)
        self.linha_badges.addWidget(Badge("Ativo" if ativo else "Inativo", "sucesso" if ativo else "erro"))
        if usuario.get("admin"):
            self.linha_badges.addWidget(Badge("Administrador", "info"))
        if usuario.get("dois_fatores_ativo"):
            self.linha_badges.addWidget(Badge("2FA ligado", "sucesso"))
        self.linha_badges.addStretch()

        self.combo_perfil.clear()
        self.combo_perfil.addItem("Vendedor", None)
        for perfil in self.perfis:
            self.combo_perfil.addItem(perfil["nome"], perfil["id"])
        indice = self.combo_perfil.findText(usuario.get("perfil_nome") or "Vendedor")
        self.combo_perfil.setCurrentIndex(max(indice, 0))
        # admin já pode tudo -- perfil não muda nada pra ele
        self.combo_perfil.setEnabled(not usuario.get("admin"))
        self.combo_perfil.setToolTip(
            "Administrador já tem acesso a tudo." if usuario.get("admin") else ""
        )

        self.combo_loja.clear()
        self.combo_loja.addItem("Todas as lojas", None)
        for loja in self.lojas:
            self.combo_loja.addItem(loja["nome"], loja["id"])
        self.combo_loja.setCurrentIndex(max(self.combo_loja.findData(usuario.get("loja_id")), 0))
        self.combo_loja.setVisible(len(self.lojas) > 1)
        self.lbl_loja.setVisible(len(self.lojas) > 1)

        self.bt_2fa.setText("Desativar 2FA" if usuario.get("dois_fatores_ativo") else "Ativar 2FA")
        self._botoes_acesso(usuario)

        self.painel_vazio.hide()
        self.painel_conteudo.show()

    # ======================================
    # CARREGAR / FILTRAR
    # ======================================

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)

        atual = self._usuario_atual()
        if atual is not None:
            self._selecionar_id = atual.get("id")

        rodar_em_thread(
            self,
            em_paralelo,
            (listar_usuarios,),
            (api.me,),
            (listar_perfis,),
            (listar_lojas,),
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.painel_conteudo.setEnabled(not carregando)

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(self, "Erro", f"Não foi possível carregar os usuários.\n{erro}")

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    def _ao_carregar_sucesso(self, resultado):

        usuarios, eu, perfis, lojas = resultado
        self.lojas = lojas or []
        # ativos primeiro, depois por nome -- inativo vai pro fim da fila
        self.usuarios = sorted(
            usuarios or [],
            key=lambda u: (not u.get("ativo", True), (u.get("nome") or "").lower()),
        )
        self.perfis = perfis or []
        self.meu_id = (eu or {}).get("id")

        self.tabela.blockSignals(True)
        self.tabela.clearSelection()
        self.tabela.setRowCount(len(self.usuarios))

        linha_selecionar = -1
        for linha, usuario in enumerate(self.usuarios):

            nome = usuario.get("nome") or ""
            if usuario.get("id") == self.meu_id:
                nome += "  (você)"
            item_nome = QTableWidgetItem(nome)
            item_nome.setToolTip(usuario.get("email") or "")
            self.tabela.setItem(linha, 0, item_nome)

            perfil = "Administrador" if usuario.get("admin") else (usuario.get("perfil_nome") or "Vendedor")
            item_perfil = QTableWidgetItem(perfil)
            if usuario.get("admin"):
                item_perfil.setForeground(QColor(tokens.PRIMARIA))
            self.tabela.setItem(linha, 1, item_perfil)

            ativo = usuario.get("ativo", True)
            item_status = QTableWidgetItem("● Ativo" if ativo else "● Inativo")
            item_status.setForeground(QColor(tokens.SECUNDARIA_HOVER if ativo else tokens.ERRO))
            self.tabela.setItem(linha, 2, item_status)

            if not ativo:
                for coluna in (0, 1):
                    self.tabela.item(linha, coluna).setForeground(QColor(tokens.TEXTO_TERCIARIO))

            if usuario.get("id") == self._selecionar_id:
                linha_selecionar = linha

        self.tabela.blockSignals(False)
        self._filtrar(self.busca.text())

        # recarregou depois de uma ação: continua no mesmo usuário
        if linha_selecionar >= 0:
            self.tabela.selectRow(linha_selecionar)
        self._mostrar_selecionado()

    def _filtrar(self, texto):

        texto = (texto or "").strip().lower()
        for linha, usuario in enumerate(self.usuarios):
            alvo = f"{usuario.get('nome') or ''} {usuario.get('email') or ''}".lower()
            self.tabela.setRowHidden(linha, texto not in alvo)

    def _usuario_atual(self):
        linha = self.tabela.currentRow()
        if linha < 0 or linha >= len(self.usuarios):
            return None
        if not self.tabela.selectionModel().rowIntersectsSelection(linha):
            return None
        return self.usuarios[linha]

    def _usuario_selecionado(self):

        usuario = self._usuario_atual()
        if usuario is None:
            QMessageBox.warning(self, "Aviso", "Selecione um usuário.")
        return usuario

    # ======================================
    # AÇÕES
    # ======================================

    def novo_usuario(self):

        dialogo = NovoUsuarioDialog(self.perfis, parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        self.busca.clear()
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
                f"Desativar o acesso de {usuario['nome']}?\n\n"
                "A pessoa não consegue mais entrar no sistema até ser "
                "reativada. O histórico de vendas continua guardado."
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
            QMessageBox.critical(self, "Erro", str(_erro_resposta(response)))
            # volta o combo/botões pro estado real
            self._mostrar_selecionado()

    def _ao_mutacao_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))
        self._mostrar_selecionado()

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
                f"Tornar {usuario['nome']} administrador?\n\n"
                "Administrador pode tudo: cancelar vendas, cadastrar "
                "usuários, redefinir senhas e mudar configurações."
                if novo_admin
                else f"Remover {usuario['nome']} da administração?\n\n"
                "A pessoa passa a ter só o que o perfil dela permite."
            ),
        )

        if resposta != QMessageBox.Yes:
            return

        self._atualizar_usuario_async(usuario["id"], {"admin": novo_admin})

    def definir_perfil(self):
        """O perfil agora troca direto no combo do painel (ver
        _ao_escolher_perfil); isto só abre o combo."""
        if self._usuario_selecionado() is not None:
            self.combo_perfil.setFocus()
            self.combo_perfil.showPopup()

    def _ao_escolher_perfil(self, _indice):

        usuario = self._usuario_atual()
        if usuario is None:
            return

        perfil_id = self.combo_perfil.currentData()
        atual = next(
            (p["id"] for p in self.perfis if p["nome"] == usuario.get("perfil_nome")), None
        )
        if perfil_id == atual:
            return

        self._atualizar_usuario_async(usuario["id"], {"perfil_id": perfil_id})

    def _ao_escolher_loja(self, _indice):

        usuario = self._usuario_atual()
        loja_id = self.combo_loja.currentData()
        if usuario is None or loja_id == usuario.get("loja_id"):
            return

        self._atualizar_usuario_async(usuario["id"], {"loja_id": loja_id})

    def gerenciar_perfis(self):

        dialogo = GerenciarPerfisDialog(parent=self)
        dialogo.exec()
        self.carregar()

    def ver_auditoria(self):

        dialogo = LogAuditoriaDialog(parent=self)
        dialogo.exec()

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
            QMessageBox.critical(self, "Erro", str(_erro_resposta(response)))
