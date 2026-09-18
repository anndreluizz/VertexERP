from datetime import datetime

from PySide6.QtCore import QSize, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from design.icons import icone
from design.widgets import Avatar, BotaoPerigo, BotaoSucesso
from services.aprovacao_service import aprovar, listar_pendentes, rejeitar

# intervalo do polling silencioso do sininho (so pra admin) -- nao
# precisa ser em tempo real, e so um numero no canto do icone ate o
# admin abrir o popover e ver a lista de verdade
_INTERVALO_POLL_APROVACOES_MS = 60_000


def _formatar_data_hora(texto_iso):
    try:
        return datetime.fromisoformat(texto_iso).strftime("%d/%m %H:%M")
    except (ValueError, TypeError):
        return ""


class _Popover(QWidget):
    """Base de um painel flutuante abaixo de um botão do header (usado
    tanto pra notificações quanto pro menu de perfil) — Qt.Popup fecha
    sozinho ao clicar fora, sem precisar reimplementar isso na mão."""

    def __init__(self, largura=280):

        super().__init__(None, Qt.Popup)

        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedWidth(largura)

        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 0)

        self.corpo = QFrame()
        self.corpo.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        externo.addWidget(self.corpo)

        self.layout_corpo = QVBoxLayout(self.corpo)
        self.layout_corpo.setContentsMargins(4, 4, 4, 4)
        self.layout_corpo.setSpacing(2)

    def abrir_sob(self, botao):

        ponto = botao.mapToGlobal(botao.rect().bottomRight())
        self.move(ponto.x() - self.width(), ponto.y() + 8)
        self.show()


class _BlocoClicavel(QFrame):
    """QFrame ao invés de QPushButton de propósito: QPushButton.sizeHint()
    ignora o layout filho e trunca o conteúdo — QFrame com layout dimensiona
    certo e ainda aceita :hover via QSS normalmente."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class _ItemMenu(QPushButton):

    def __init__(self, texto, icone_nome=None, perigo=False):

        super().__init__(texto)

        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)

        if icone_nome:
            self.setIcon(icone(
                icone_nome,
                cor=tokens.ERRO if perigo else tokens.TEXTO_SECUNDARIO,
                tamanho=16,
            ))

        cor_texto = tokens.ERRO if perigo else tokens.TEXTO

        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding-left: 10px;
                border: none;
                border-radius: {tokens.RADIUS_SM}px;
                color: {cor_texto};
                font-size: {tokens.TAMANHO_MD}px;
                background: transparent;
            }}
            QPushButton:hover {{
                background: {tokens.FUNDO};
            }}
        """)


class _CartaoAprovacao(QFrame):
    """Um pedido de aprovação pendente dentro do popover do sino --
    descrição + Aprovar/Rejeitar, cada um chamando a API na hora e
    avisando o Header (via on_resolvido) pra tirar o card da lista e
    atualizar o badge de contagem."""

    def __init__(self, solicitacao, on_resolvido, parent=None):

        super().__init__(parent)

        self._solicitacao_id = solicitacao["id"]
        self._on_resolvido = on_resolvido

        self.setStyleSheet(f"""
            QFrame {{
                background: {tokens.FUNDO};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        lbl_data = QLabel(_formatar_data_hora(solicitacao.get("criado_em", "")))
        lbl_data.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)
        layout.addWidget(lbl_data)

        lbl_desc = QLabel(solicitacao.get("descricao", ""))
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(lbl_desc)

        botoes = QHBoxLayout()
        botoes.setSpacing(6)

        self.bt_rejeitar = BotaoPerigo("Rejeitar")
        self.bt_rejeitar.setMinimumHeight(30)
        self.bt_rejeitar.clicked.connect(lambda: self._responder(False))

        self.bt_aprovar = BotaoSucesso("Aprovar")
        self.bt_aprovar.setMinimumHeight(30)
        self.bt_aprovar.clicked.connect(lambda: self._responder(True))

        botoes.addWidget(self.bt_rejeitar)
        botoes.addWidget(self.bt_aprovar)

        layout.addLayout(botoes)

    def _responder(self, deve_aprovar):

        self.bt_aprovar.setEnabled(False)
        self.bt_rejeitar.setEnabled(False)

        try:
            response = (
                aprovar(self._solicitacao_id)
                if deve_aprovar
                else rejeitar(self._solicitacao_id)
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            self.bt_aprovar.setEnabled(True)
            self.bt_rejeitar.setEnabled(True)
            return

        if response.status_code != 200:

            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))
            self.bt_aprovar.setEnabled(True)
            self.bt_rejeitar.setEnabled(True)
            return

        self._on_resolvido(self)


class Header(QFrame):

    busca_alterada = Signal(str)
    tema_alternado = Signal(bool)
    solicitou_logout = Signal()
    solicitou_trocar_senha = Signal()

    def __init__(self, nome_loja, nome_usuario, cargo, admin=False, parent=None):

        super().__init__(parent)

        # reflete o tema que ja esta ativo (ver design.tokens.aplicar,
        # chamado no arranque do app) -- sem isso o botao sempre
        # nascia mostrando o icone de "mudar pra escuro" mesmo quando
        # o escuro ja estava ligado
        self._modo_escuro = tokens.ESCURO_ATIVO

        # so admin pode ver/agir em aprovacoes pendentes (a API bloqueia
        # com 403 pra qualquer outro usuario) -- pra quem nao e admin,
        # o sino continua so um enfeite sem nada pra mostrar
        self._admin = admin

        self.setFixedHeight(64)
        self.setStyleSheet(f"""
            Header {{
                background: {tokens.CARD};
                border-bottom: 1px solid {tokens.BORDA};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 20, 0)
        layout.setSpacing(16)

        self.lbl_titulo = QLabel("Início")
        self.lbl_titulo.setStyleSheet(f"""
            background: transparent;
            color: {tokens.TEXTO};
            font-size: {tokens.TAMANHO_XL}px;
            font-weight: 700;
        """)
        layout.addWidget(self.lbl_titulo)

        # ======================
        # STATUS DE CONEXAO -- escondido por padrao (assume online, ver
        # PrincipalWindow); some/aparece sozinho conforme a checagem
        # periodica de fundo, nunca precisa de acao do usuario.
        # ======================

        self.lbl_status_conexao = QLabel("⏺  Sem conexão com o servidor — tentando reconectar…")
        self.lbl_status_conexao.setStyleSheet(f"""
            background: {tokens.ERRO_CLARO};
            color: {tokens.ERRO};
            font-size: {tokens.TAMANHO_SM}px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: {tokens.RADIUS_SM}px;
        """)
        self.lbl_status_conexao.setVisible(False)
        layout.addWidget(self.lbl_status_conexao)

        # ======================
        # BUSCA GLOBAL
        # ======================

        busca_container = QFrame()
        busca_container.setFixedHeight(38)
        busca_container.setMinimumWidth(280)
        busca_container.setStyleSheet(f"""
            QFrame {{
                background: {tokens.FUNDO};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

        busca_layout = QHBoxLayout(busca_container)
        busca_layout.setContentsMargins(10, 0, 10, 0)
        busca_layout.setSpacing(6)

        lbl_lupa = QLabel()
        lbl_lupa.setPixmap(
            icone(
                "search", cor=tokens.TEXTO_TERCIARIO, tamanho=16
            ).pixmap(16, 16)
        )
        lbl_lupa.setStyleSheet("background:transparent;")

        self.campo_busca = QLineEdit()
        self.campo_busca.setPlaceholderText("Buscar produtos, clientes, vendas...")
        self.campo_busca.setStyleSheet(f"""
            QLineEdit {{
                border: none;
                background: transparent;
                color: {tokens.TEXTO};
                font-size: {tokens.TAMANHO_BASE}px;
            }}
        """)
        self.campo_busca.textChanged.connect(self.busca_alterada)

        busca_layout.addWidget(lbl_lupa)
        busca_layout.addWidget(self.campo_busca, stretch=1)

        layout.addWidget(busca_container, stretch=1)

        # ======================
        # RELÓGIO
        # ======================

        self.lbl_relogio = QLabel()
        self.lbl_relogio.setStyleSheet(f"""
            background: transparent;
            color: {tokens.TEXTO_SECUNDARIO};
            font-size: {tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(self.lbl_relogio)

        self._timer_relogio = QTimer(self)
        self._timer_relogio.timeout.connect(self._atualizar_relogio)
        self._timer_relogio.start(1000)
        self._atualizar_relogio()

        # ======================
        # TEMA / NOTIFICAÇÕES / PERFIL
        # ======================

        self.bt_tema = self._botao_icone(
            "sun" if self._modo_escuro else "moon"
        )
        self.bt_tema.setToolTip("Alternar tema claro/escuro")
        self.bt_tema.clicked.connect(self._alternar_tema)
        layout.addWidget(self.bt_tema)

        self.bt_notificacoes = self._botao_icone("bell")
        self.bt_notificacoes.setToolTip("Notificações")
        self.bt_notificacoes.clicked.connect(self._abrir_notificacoes)
        layout.addWidget(self.bt_notificacoes)

        # bolinha vermelha com a contagem, sobreposta no canto do sino
        # -- filha do proprio botao pra nao precisar de layout proprio,
        # so uma geometria fixa (o botao tem tamanho fixo 38x38)
        self._badge_aprovacoes = QLabel(self.bt_notificacoes)
        self._badge_aprovacoes.setGeometry(22, 1, 17, 17)
        self._badge_aprovacoes.setAlignment(Qt.AlignCenter)
        self._badge_aprovacoes.setStyleSheet(f"""
            background: {tokens.ERRO};
            color: {tokens.TEXTO_CLARO};
            border-radius: 8px;
            font-size: 9px;
            font-weight: 700;
        """)
        self._badge_aprovacoes.hide()

        self._timer_aprovacoes = None

        if self._admin:
            self._atualizar_contagem_aprovacoes()

            self._timer_aprovacoes = QTimer(self)
            self._timer_aprovacoes.timeout.connect(
                self._atualizar_contagem_aprovacoes
            )
            self._timer_aprovacoes.start(_INTERVALO_POLL_APROVACOES_MS)

        divisor = QFrame()
        divisor.setFixedSize(1, 32)
        divisor.setStyleSheet(f"background:{tokens.BORDA};")
        layout.addWidget(divisor)

        self.bt_perfil = _BlocoClicavel()
        self.bt_perfil.setFixedHeight(44)
        self.bt_perfil.setStyleSheet(f"""
            _BlocoClicavel {{
                border: none;
                border-radius: {tokens.RADIUS_SM}px;
                background: transparent;
            }}
            _BlocoClicavel:hover {{
                background: {tokens.FUNDO};
            }}
        """)

        perfil_layout = QHBoxLayout(self.bt_perfil)
        perfil_layout.setContentsMargins(8, 0, 12, 0)
        perfil_layout.setSpacing(8)

        avatar = Avatar(nome_usuario, tamanho=34)
        perfil_layout.addWidget(avatar)

        col_perfil = QVBoxLayout()
        col_perfil.setSpacing(0)

        lbl_nome = QLabel(nome_usuario)
        lbl_nome.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)

        lbl_cargo = QLabel(cargo)
        lbl_cargo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        col_perfil.addWidget(lbl_nome)
        col_perfil.addWidget(lbl_cargo)

        perfil_layout.addLayout(col_perfil)

        self.bt_perfil.clicked.connect(self._abrir_menu_perfil)

        layout.addWidget(self.bt_perfil)

        self._popover_notificacoes = None
        self._popover_perfil = None

    def _botao_icone(self, nome_icone):

        botao = QPushButton()
        botao.setFixedSize(38, 38)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setIcon(icone(nome_icone, cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
        botao.setIconSize(QSize(18, 18))
        botao.setStyleSheet(f"""
            QPushButton {{
                border: none;
                border-radius: {tokens.RADIUS_SM}px;
                background: transparent;
            }}
            QPushButton:hover {{
                background: {tokens.FUNDO};
            }}
        """)
        return botao

    def definir_titulo(self, texto):
        self.lbl_titulo.setText(texto)

    def definir_online(self, online: bool):
        """Chamado pela checagem periodica de conectividade em segundo
        plano (ver PrincipalWindow) -- so troca a visibilidade do
        aviso, nada mais (nunca desabilita nada aqui: cada tela ja
        trata falha de rede na hora H, isso e so um indicador)."""
        self.lbl_status_conexao.setVisible(not online)

    def _atualizar_relogio(self):
        agora = datetime.now()
        dias = [
            "segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo",
        ]
        self.lbl_relogio.setText(
            f"{dias[agora.weekday()]}, {agora.strftime('%d/%m/%Y')} · "
            f"{agora.strftime('%H:%M:%S')}"
        )

    def _alternar_tema(self):
        self._modo_escuro = not self._modo_escuro
        self.bt_tema.setIcon(
            icone(
                "sun" if self._modo_escuro else "moon",
                cor=tokens.TEXTO_SECUNDARIO,
                tamanho=18,
            )
        )
        self.tema_alternado.emit(self._modo_escuro)

    def _atualizar_contagem_aprovacoes(self):

        try:
            pendentes = listar_pendentes()
        except Exception:
            # sem servidor/rede -- so deixa o badge como estava, nao
            # vale a pena incomodar o usuario por causa do polling
            return

        total = len(pendentes)

        if total:
            self._badge_aprovacoes.setText(str(total) if total <= 9 else "9+")
            self._badge_aprovacoes.show()
        else:
            self._badge_aprovacoes.hide()

    def _abrir_notificacoes(self):

        popover = _Popover(largura=320)

        titulo = QLabel("Notificações")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:700;
            padding: 8px 10px 4px 10px;
        """)
        popover.layout_corpo.addWidget(titulo)

        self._popover_notificacoes = popover

        if not self._admin:

            vazio = QLabel("Nenhuma notificação por enquanto.")
            vazio.setWordWrap(True)
            vazio.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_SM}px; padding: 4px 10px 12px 10px;
            """)
            popover.layout_corpo.addWidget(vazio)

            popover.abrir_sob(self.bt_notificacoes)
            return

        subtitulo = QLabel("Aprovações pendentes")
        subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
            padding: 0 10px 6px 10px;
        """)
        popover.layout_corpo.addWidget(subtitulo)

        try:
            pendentes = listar_pendentes()
        except Exception:
            pendentes = None

        if pendentes is None:
            erro = QLabel("Não foi possível carregar as aprovações.")
            erro.setWordWrap(True)
            erro.setStyleSheet(f"""
                background:transparent; color:{tokens.ERRO};
                font-size:{tokens.TAMANHO_SM}px; padding: 4px 10px 12px 10px;
            """)
            popover.layout_corpo.addWidget(erro)
        elif not pendentes:
            vazio = QLabel("Nenhuma aprovação pendente no momento.")
            vazio.setWordWrap(True)
            vazio.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_SM}px; padding: 4px 10px 12px 10px;
            """)
            popover.layout_corpo.addWidget(vazio)
        else:
            for solicitacao in pendentes:
                popover.layout_corpo.addWidget(
                    _CartaoAprovacao(solicitacao, on_resolvido=self._ao_resolver_aprovacao)
                )

        popover.abrir_sob(self.bt_notificacoes)

    def _ao_resolver_aprovacao(self, cartao):
        """Chamado por um _CartaoAprovacao depois de aprovar/rejeitar
        com sucesso -- tira o card do popover e atualiza o badge."""

        cartao.setParent(None)
        cartao.deleteLater()

        self._atualizar_contagem_aprovacoes()

    def _abrir_menu_perfil(self):

        popover = _Popover(largura=200)

        item_senha = _ItemMenu("Trocar Senha", icone_nome="lock")
        item_senha.clicked.connect(popover.close)
        item_senha.clicked.connect(self.solicitou_trocar_senha)

        item_sair = _ItemMenu("Sair", icone_nome="log-out", perigo=True)
        item_sair.clicked.connect(popover.close)
        item_sair.clicked.connect(self.solicitou_logout)

        popover.layout_corpo.addWidget(item_senha)
        popover.layout_corpo.addWidget(item_sair)

        self._popover_perfil = popover
        popover.abrir_sob(self.bt_perfil)
