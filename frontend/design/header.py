from datetime import datetime

from PySide6.QtCore import QSize, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from design import tokens
from design.privacidade import privacidade
from design.icons import icone
from design.widgets import Avatar, Badge, BotaoPerigo, BotaoPrimario, BotaoSecundario, BotaoSucesso
from services.aprovacao_service import aprovar, listar_pendentes, rejeitar
from services import notificacao_service

# intervalo do polling silencioso do sininho -- nao precisa ser em
# tempo real, e so um numero no canto do icone ate o usuario abrir o
# popover e ver a lista de verdade. Aprovacoes so' existe pra admin
# (API bloqueia com 403 pra qualquer outro), notificacoes sao pra
# todo mundo.
_INTERVALO_POLL_APROVACOES_MS = 60_000
_INTERVALO_POLL_NOTIFICACOES_MS = 30_000

# quanto tempo o alerta de notificacao nova fica no canto da tela
_ALERTA_MS = 8_000


def _tocar_som():
    try:
        import winsound

        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        QApplication.beep()


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
        self.corpo.setObjectName("popoverCorpo")
        self.corpo.setStyleSheet(f"""
            QFrame#popoverCorpo {{
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
                background: {tokens.ALERTA_CLARO};
                border-radius: {tokens.RADIUS_SM + 2}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        lbl_data = QLabel(
            "PEDIDO DE APROVAÇÃO · " + _tempo_relativo(solicitacao.get("criado_em", "")).upper()
        )
        lbl_data.setStyleSheet(f"""
            background:transparent; color:{tokens.ALERTA_TEXTO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)
        layout.addWidget(lbl_data)

        lbl_desc = QLabel(solicitacao.get("descricao", ""))
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_BASE}px; font-weight:600;
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


# ---------------------------------------------------------------------
# CENTRAL DE NOTIFICAÇÕES (sino)
# ---------------------------------------------------------------------

# assunto da notificação, deduzido do título (o backend não guarda tipo):
# (palavra-chave, ícone, tom)
_CATEGORIAS = (
    ("caixa", "wallet", "pri"), ("conta", "file-text", "alerta"),
    ("boleto", "file-text", "alerta"), ("vencimento", "calendar", "alerta"),
    ("vence", "calendar", "alerta"), ("backup", "download", "erro"),
    ("cliente", "users", "ok"), ("fiado", "users", "ok"),
    ("estoque", "package", "alerta"), ("aprova", "lock", "pri"),
)


def _categoria(titulo):
    t = (titulo or "").lower()
    for chave, nome_icone, tom in _CATEGORIAS:
        if chave in t:
            return nome_icone, tom
    return "bell", "pri"


def _cores_do_tom(tom):
    return {
        "pri": (tokens.PRIMARIA_CLARA, tokens.PRIMARIA),
        "ok": (tokens.SUCESSO_CLARO, tokens.SUCESSO),
        "alerta": (tokens.ALERTA_CLARO, tokens.ALERTA),
        "erro": (tokens.ERRO_CLARO, tokens.ERRO),
    }[tom]


def _minutos_desde(texto_iso):
    try:
        return max(0, int((datetime.now() - datetime.fromisoformat(texto_iso)).total_seconds() // 60))
    except (ValueError, TypeError):
        return None


def _tempo_relativo(texto_iso):
    m = _minutos_desde(texto_iso)
    if m is None:
        return ""
    if m < 1:
        return "agora"
    if m < 60:
        return f"há {m} min"
    if m < 60 * 24:
        return f"há {m // 60} h"
    return f"há {m // (60 * 24)} d"


def _grupo_do_dia(texto_iso):
    m = _minutos_desde(texto_iso)
    if m is None or m < 60 * 24:
        return "Hoje"
    return "Ontem" if m < 60 * 48 else "Antes"


class _CartaoNotificacao(_BlocoClicavel):
    """Uma notificação da central: ícone do assunto, título, texto, tempo
    relativo e bolinha de não lida. Clicar marca como lida na hora."""

    def __init__(self, notificacao, on_lida, parent=None):

        super().__init__(parent)

        self._notificacao = notificacao
        self._notificacao_id = notificacao["id"]
        self._lida = notificacao["lida"]
        self._on_lida = on_lida

        self._aplicar_estilo()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        nome_icone, tom = _categoria(notificacao["titulo"])
        fundo_tom, cor_tom = _cores_do_tom(tom)
        if tom == "pri" and not self._lida:
            fundo_tom = tokens.CARD  # senão some no fundo azul-claro de "não lida"
        bola = QLabel()
        bola.setFixedSize(38, 38)
        bola.setAlignment(Qt.AlignCenter)
        bola.setPixmap(icone(nome_icone, cor=cor_tom, tamanho=19).pixmap(19, 19))
        bola.setStyleSheet(f"background:{fundo_tom}; border:none; border-radius:19px;")
        layout.addWidget(bola, 0, Qt.AlignTop)

        coluna = QVBoxLayout()
        coluna.setSpacing(2)

        self.lbl_titulo = QLabel(notificacao["titulo"])
        self.lbl_titulo.setWordWrap(True)
        coluna.addWidget(self.lbl_titulo)

        lbl_corpo = QLabel(notificacao["corpo"])
        lbl_corpo.setWordWrap(True)
        lbl_corpo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        coluna.addWidget(lbl_corpo)

        lbl_tempo = QLabel(_tempo_relativo(notificacao.get("criado_em", "")))
        lbl_tempo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)
        coluna.addWidget(lbl_tempo)
        layout.addLayout(coluna, 1)

        self.ponto = QLabel()
        self.ponto.setFixedSize(10, 10)
        self.ponto.setStyleSheet(f"background:{tokens.PRIMARIA}; border:none; border-radius:5px;")
        layout.addWidget(self.ponto, 0, Qt.AlignTop)

        self._pintar_titulo()
        self.clicked.connect(self._marcar_lida)

    def _pintar_titulo(self):
        self.ponto.setVisible(not self._lida)
        self.lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_BASE}px; font-weight:{500 if self._lida else 700};
        """)

    def _aplicar_estilo(self):
        fundo = "transparent" if self._lida else tokens.PRIMARIA_CLARA
        self.setStyleSheet(f"""
            _CartaoNotificacao {{
                background: {fundo};
                border-radius: {tokens.RADIUS_SM + 2}px;
            }}
            _CartaoNotificacao:hover {{
                background: {tokens.FUNDO};
            }}
        """)

    def _marcar_lida(self):

        if self._lida:
            return

        try:
            notificacao_service.marcar_lida(self._notificacao_id)
        except Exception:
            return

        self._lida = True
        self._notificacao["lida"] = True
        self._aplicar_estilo()
        self._pintar_titulo()
        self._on_lida()


class _AlertaNotificacao(QFrame):
    """Alerta no canto inferior direito da tela quando chega notificação
    nova (o número no sino sozinho passava despercebido). Janela própria,
    por cima das outras, pra aparecer mesmo com o Vertex minimizado; some
    sozinha. "Ver" abre o sino, "Dispensar" fecha."""

    def __init__(self, titulo, corpo, ao_clicar):
        super().__init__(
            None,
            Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedWidth(380)
        self.setObjectName("alertaNotificacao")
        self._ao_clicar = ao_clicar
        self.setStyleSheet(f"""
            QFrame#alertaNotificacao {{
                background: {tokens.CARD};
                border: 1px solid {tokens.BORDA_FORTE};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        nome_icone, tom = _categoria(titulo)
        fundo_tom, cor_tom = _cores_do_tom(tom)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 12, 12)
        layout.setSpacing(12)

        bola = QLabel()
        bola.setFixedSize(40, 40)
        bola.setAlignment(Qt.AlignCenter)
        bola.setPixmap(icone(nome_icone, cor=cor_tom, tamanho=20).pixmap(20, 20))
        bola.setStyleSheet(f"background:{fundo_tom}; border:none; border-radius:20px;")
        layout.addWidget(bola, 0, Qt.AlignTop)

        coluna = QVBoxLayout()
        coluna.setSpacing(2)

        def rotulo(texto, tamanho, cor, peso=400):
            lbl = QLabel(texto)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(f"""
                background:transparent; border:none; color:{cor};
                font-size:{tamanho}px; font-weight:{peso};
            """)
            return lbl

        coluna.addWidget(rotulo("Vertex · agora", tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO, 600))
        coluna.addWidget(rotulo(titulo, tokens.TAMANHO_BASE, tokens.TEXTO, 700))
        coluna.addWidget(rotulo(corpo, tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO))

        botoes = QHBoxLayout()
        botoes.setSpacing(8)
        self.bt_ver = BotaoPrimario("Ver")
        self.bt_ver.setMinimumHeight(30)
        self.bt_ver.clicked.connect(self._ver)
        self.bt_dispensar = BotaoSecundario("Dispensar")
        self.bt_dispensar.setMinimumHeight(30)
        self.bt_dispensar.clicked.connect(self.close)
        botoes.addWidget(self.bt_ver)
        botoes.addWidget(self.bt_dispensar)
        botoes.addStretch()
        coluna.addSpacing(4)
        coluna.addLayout(botoes)
        layout.addLayout(coluna, 1)

        QTimer.singleShot(_ALERTA_MS, self.close)

    def _ver(self):
        self.close()
        self._ao_clicar()

    def mostrar(self):
        self.adjustSize()
        tela = QApplication.primaryScreen()
        if tela is not None:
            area = tela.availableGeometry()
            self.move(
                area.right() - self.width() - 16,
                area.bottom() - self.height() - 16,
            )
        self.show()


class _Central(_Popover):
    """Painel do sino: abas (Todas / Não lidas / Aprovações), pedidos de
    aprovação no topo (admin) e as notificações agrupadas por dia."""

    def __init__(self, header, notificacoes, pendentes):

        super().__init__(largura=420)

        self._header = header
        self.notificacoes = notificacoes   # None = falhou ao carregar
        self.pendentes = pendentes         # None = falhou; [] sem admin
        self.aba = "todas"
        self.layout_corpo.setContentsMargins(14, 14, 14, 10)
        self.layout_corpo.setSpacing(10)
        self._montar()

    def _montar(self):

        while self.layout_corpo.count():
            item = self.layout_corpo.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout():
                self._esvaziar(item.layout())
                item.layout().deleteLater()

        admin = self._header._admin
        nao_lidas = sum(1 for n in (self.notificacoes or []) if not n["lida"])
        n_aprov = len(self.pendentes or [])

        topo = QHBoxLayout()
        topo.setSpacing(8)
        titulo = QLabel("Notificações")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_LG}px; font-weight:700;
        """)
        topo.addWidget(titulo)
        if nao_lidas:
            topo.addWidget(Badge(f"{nao_lidas} novas", "info"), 0, Qt.AlignVCenter)
        topo.addStretch()
        if nao_lidas:
            bt = QPushButton("Marcar todas como lidas")
            bt.setCursor(Qt.PointingHandCursor)
            bt.setStyleSheet(f"""
                QPushButton {{ background:transparent; border:none; color:{tokens.PRIMARIA};
                               font-size:{tokens.TAMANHO_SM}px; font-weight:600; }}
                QPushButton:hover {{ text-decoration:underline; }}
            """)
            bt.clicked.connect(self._header._marcar_todas_notificacoes_lidas)
            topo.addWidget(bt)
        self.layout_corpo.addLayout(topo)

        abas = QHBoxLayout()
        abas.setSpacing(8)
        opcoes = [("todas", "Todas"), ("nao", f"Não lidas  {nao_lidas}")]
        if admin:
            opcoes.append(("aprov", f"Aprovações  {n_aprov}"))
        for chave, texto in opcoes:
            ativo = chave == self.aba
            chip = QPushButton(texto)
            chip.setFixedHeight(32)
            chip.setCursor(Qt.PointingHandCursor)
            chip.setStyleSheet(f"""
                QPushButton {{ padding:0 14px; border-radius:16px; font-size:{tokens.TAMANHO_SM}px;
                    font-weight:{700 if ativo else 600};
                    border:1px solid {tokens.PRIMARIA_CLARA if ativo else tokens.BORDA};
                    background:{tokens.PRIMARIA_CLARA if ativo else tokens.CARD};
                    color:{tokens.PRIMARIA if ativo else tokens.TEXTO_SECUNDARIO}; }}
            """)
            chip.clicked.connect(lambda _=False, c=chave: self._trocar_aba(c))
            abas.addWidget(chip)
        abas.addStretch()
        self.layout_corpo.addLayout(abas)

        lista = QWidget()
        lista.setStyleSheet("background:transparent;")
        lv = QVBoxLayout(lista)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(2)

        linhas = 0
        if admin and self.aba in ("todas", "aprov"):
            if self.pendentes is None:
                lv.addWidget(self._aviso("Não foi possível carregar as aprovações.", erro=True))
                linhas += 1
            for solicitacao in self.pendentes or []:
                lv.addWidget(_CartaoAprovacao(solicitacao, on_resolvido=self._ao_resolver))
                linhas += 2

        if self.aba != "aprov":
            if self.notificacoes is None:
                lv.addWidget(self._aviso("Não foi possível carregar as notificações.", erro=True))
                linhas += 1
            else:
                itens = [n for n in self.notificacoes if self.aba == "todas" or not n["lida"]]
                ultimo = None
                for n in itens:
                    grupo = _grupo_do_dia(n.get("criado_em", ""))
                    if grupo != ultimo:
                        lv.addSpacing(4)
                        rot = QLabel(grupo.upper())
                        rot.setStyleSheet(f"""
                            background:transparent; color:{tokens.TEXTO_TERCIARIO};
                            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
                        """)
                        lv.addWidget(rot)
                        ultimo = grupo
                    lv.addWidget(_CartaoNotificacao(n, on_lida=self._ao_ler))
                    linhas += 2
                if not itens and not linhas:
                    lv.addWidget(self._vazio())
                    linhas += 4
        elif not self.pendentes and self.pendentes is not None:
            lv.addWidget(self._vazio("Nenhuma aprovação pendente.", "lock"))
            linhas += 4

        lv.addStretch()

        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QFrame.NoFrame)
        rolagem.setStyleSheet("QScrollArea { background:transparent; border:none; }")
        rolagem.setWidget(lista)
        rolagem.setFixedHeight(max(150, min(440, 40 + 40 * max(1, linhas))))
        self.layout_corpo.addWidget(rolagem)

    @staticmethod
    def _esvaziar(layout):
        while layout.count():
            widget = layout.takeAt(0).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    @staticmethod
    def _aviso(texto, erro=False):
        lbl = QLabel(texto)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"""
            background:transparent; color:{tokens.ERRO if erro else tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; padding: 4px 10px 12px 10px;
        """)
        return lbl

    @staticmethod
    def _vazio(texto="Tudo em dia por aqui.", nome_icone="bell"):
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 28, 0, 28)
        v.setSpacing(6)
        bola = QLabel()
        bola.setFixedSize(52, 52)
        bola.setAlignment(Qt.AlignCenter)
        bola.setPixmap(icone(nome_icone, cor=tokens.PRIMARIA, tamanho=24).pixmap(24, 24))
        bola.setStyleSheet(f"background:{tokens.PRIMARIA_CLARA}; border-radius:26px;")
        v.addWidget(bola, 0, Qt.AlignCenter)
        for t, tam, cor, peso in (
            (texto, tokens.TAMANHO_BASE, tokens.TEXTO, 600),
            ("Quando algo precisar de você, aparece aqui.", tokens.TAMANHO_SM, tokens.TEXTO_TERCIARIO, 400),
        ):
            lbl = QLabel(t)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"background:transparent; color:{cor}; font-size:{tam}px; font-weight:{peso};")
            v.addWidget(lbl)
        return w

    def _trocar_aba(self, chave):
        self.aba = chave
        self._montar()

    def _ao_ler(self):
        self._header._atualizar_contagem_notificacoes()
        QTimer.singleShot(0, self._montar)  # depois do clique terminar

    def _ao_resolver(self, cartao):
        self.pendentes = [p for p in (self.pendentes or []) if p["id"] != cartao._solicitacao_id]
        self._header._atualizar_contagem_aprovacoes()
        QTimer.singleShot(0, self._montar)

    def marcar_todas_lidas(self):
        for n in self.notificacoes or []:
            n["lida"] = True
        self._montar()


class Header(QFrame):

    busca_alterada = Signal(str)
    tema_alternado = Signal(bool)
    solicitou_logout = Signal()
    solicitou_trocar_senha = Signal()
    solicitou_configuracoes = Signal()

    def __init__(self, nome_loja, nome_usuario, cargo, admin=False, parent=None,
                 na_barra=False):
        """na_barra=True: vira so' o bloco da direita da barra clara do
        topo (olhinho, sino, perfil, aviso de conexao) -- titulo, busca,
        relogio e tema ficam escondidos (ver design/navegacao.py)."""

        super().__init__(parent)

        self._na_barra = na_barra
        self._cor_icone = tokens.TEXTO_SECUNDARIO
        # na faixa de abas o fundo ja' e' FUNDO: o hover precisa de outro tom
        self._fundo_hover = tokens.BORDA if na_barra else tokens.FUNDO

        # reflete o tema que ja esta ativo (ver design.tokens.aplicar,
        # chamado no arranque do app) -- sem isso o botao sempre
        # nascia mostrando o icone de "mudar pra escuro" mesmo quando
        # o escuro ja estava ligado
        self._modo_escuro = tokens.ESCURO_ATIVO

        # so admin pode ver/agir em aprovacoes pendentes (a API bloqueia
        # com 403 pra qualquer outro usuario) -- pra quem nao e admin,
        # o sino continua so um enfeite sem nada pra mostrar
        self._admin = admin

        self.setFixedHeight(56 if na_barra else 64)
        if na_barra:
            # so' o tamanho dos botoes -- sem isso o bloco disputa a folga da barra
            # com o stretch e o avatar nao cola na direita
            self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setStyleSheet(
            "Header { background: transparent; border: none; }" if na_barra else f"""
            Header {{
                background: {tokens.CARD};
                border-bottom: 1px solid {tokens.BORDA};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(*((0, 0, 0, 0) if na_barra else (24, 0, 20, 0)))
        layout.setSpacing(8 if na_barra else 16)

        self.lbl_titulo = QLabel("Início")
        self.lbl_titulo.setStyleSheet(f"""
            background: transparent;
            color: {tokens.TEXTO};
            font-size: {tokens.TAMANHO_XL}px;
            font-weight: 700;
        """)
        layout.addWidget(self.lbl_titulo)
        self.lbl_titulo.setVisible(not na_barra)

        # ======================
        # STATUS DE CONEXAO -- escondido por padrao (assume online, ver
        # PrincipalWindow); some/aparece sozinho conforme a checagem
        # periodica de fundo, nunca precisa de acao do usuario.
        # ======================

        self.lbl_status_conexao = QLabel("Sem conexão com o servidor — tentando reconectar…")
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
        busca_container.setVisible(not na_barra)

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
        self.lbl_relogio.setVisible(not na_barra)

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
        # na barra azul nao cabe: o tema vai pro menu do perfil
        self.bt_tema.setVisible(not na_barra)

        # olhinho: esconde/mostra os valores em dinheiro (cards, caixa)
        # pra cliente no balcao nao ver -- ver design/privacidade.py
        self.bt_valores = self._botao_icone("eye-off")
        self.bt_valores.clicked.connect(privacidade.alternar)
        privacidade.mudou.connect(self._atualizar_olho)
        self._atualizar_olho(privacidade.ocultos)
        layout.addWidget(self.bt_valores)

        self.bt_notificacoes = self._botao_icone("bell")
        self.bt_notificacoes.setToolTip("Notificações")
        self.bt_notificacoes.clicked.connect(self._abrir_notificacoes)
        layout.addWidget(self.bt_notificacoes)

        # bolinha vermelha com a contagem total (aprovacoes pendentes +
        # notificacoes nao lidas), sobreposta no canto do sino -- filha
        # do proprio botao pra nao precisar de layout proprio, so uma
        # geometria fixa (o botao tem tamanho fixo 38x38)
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

        self._total_aprovacoes = 0
        self._total_nao_lidas = 0
        # maior id de notificacao ja visto -- None ate a primeira
        # consulta, pra nao alertar as antigas ao abrir o sistema
        self._ultima_notificacao_id = None
        self._alerta = None

        self._timer_aprovacoes = None

        if self._admin:
            self._atualizar_contagem_aprovacoes()

            self._timer_aprovacoes = QTimer(self)
            self._timer_aprovacoes.timeout.connect(
                self._atualizar_contagem_aprovacoes
            )
            self._timer_aprovacoes.start(_INTERVALO_POLL_APROVACOES_MS)

        self._atualizar_contagem_notificacoes()

        self._timer_notificacoes = QTimer(self)
        self._timer_notificacoes.timeout.connect(
            self._atualizar_contagem_notificacoes
        )
        self._timer_notificacoes.start(_INTERVALO_POLL_NOTIFICACOES_MS)

        # engrenagem: atalho pra Configurações (só admin -- é quem pode abrir)
        self.bt_config = self._botao_icone("settings")
        self.bt_config.setToolTip("Configurações")
        self.bt_config.setAccessibleName("Configurações")
        self.bt_config.clicked.connect(self.solicitou_configuracoes.emit)
        self.bt_config.setVisible(bool(self._admin))
        layout.addWidget(self.bt_config)

        divisor = QFrame()
        divisor.setFixedSize(1, 32)
        divisor.setStyleSheet(f"background:{tokens.BORDA};")
        layout.addWidget(divisor)
        divisor.setVisible(not na_barra)

        self.bt_perfil = _BlocoClicavel()
        self.bt_perfil.setFixedHeight(44)
        self.bt_perfil.setStyleSheet(f"""
            _BlocoClicavel {{
                border: none;
                border-radius: {tokens.RADIUS_SM}px;
                background: transparent;
            }}
            _BlocoClicavel:hover {{
                background: {self._fundo_hover};
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
        if na_barra:
            # so' o avatar na barra (nome e cargo aparecem no menu)
            lbl_nome.hide()
            lbl_cargo.hide()
            perfil_layout.setContentsMargins(4, 0, 4, 0)
            self.bt_perfil.setToolTip(f"{nome_usuario} · {cargo}")
        self._nome_usuario, self._cargo = nome_usuario, cargo

        self.bt_perfil.clicked.connect(self._abrir_menu_perfil)

        layout.addWidget(self.bt_perfil)

        self._popover_notificacoes = None
        self._popover_perfil = None

    def _botao_icone(self, nome_icone):

        botao = QPushButton()
        botao.setFixedSize(38, 38)
        botao.setCursor(Qt.PointingHandCursor)
        botao.setIcon(icone(nome_icone, cor=self._cor_icone, tamanho=18))
        botao.setIconSize(QSize(18, 18))
        botao.setStyleSheet(f"""
            QPushButton {{
                border: none;
                border-radius: {tokens.RADIUS_SM}px;
                background: transparent;
            }}
            QPushButton:hover {{
                background: {self._fundo_hover};
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

    def _atualizar_olho(self, ocultos):
        self.bt_valores.setIcon(
            icone("eye-off" if ocultos else "eye", cor=self._cor_icone, tamanho=18)
        )
        self.bt_valores.setToolTip("Mostrar valores" if ocultos else "Ocultar valores")

    def _alternar_tema(self):
        self._modo_escuro = not self._modo_escuro
        self.bt_tema.setIcon(
            icone(
                "sun" if self._modo_escuro else "moon",
                cor=self._cor_icone,
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

        self._total_aprovacoes = len(pendentes)
        self._atualizar_badge()

    def _atualizar_contagem_notificacoes(self):

        try:
            self._total_nao_lidas = notificacao_service.contagem_nao_lidas()
        except Exception:
            # mesmo espirito de _atualizar_contagem_aprovacoes -- sem
            # servidor/rede, so deixa o badge como estava
            return

        self._atualizar_badge()
        self._alertar_novas()

    def _alertar_novas(self):

        try:
            recentes = notificacao_service.listar(limit=10)
        except Exception:
            return

        if not recentes:
            if self._ultima_notificacao_id is None:
                self._ultima_notificacao_id = 0
            return

        maior = max(n["id"] for n in recentes)

        if self._ultima_notificacao_id is None:
            self._ultima_notificacao_id = maior
            return

        novas = [
            n for n in recentes
            if n["id"] > self._ultima_notificacao_id and not n["lida"]
        ]
        self._ultima_notificacao_id = max(maior, self._ultima_notificacao_id)

        if not novas:
            return

        mais_nova = max(novas, key=lambda n: n["id"])
        titulo = mais_nova["titulo"]
        if len(novas) > 1:
            titulo = f"{titulo} (+{len(novas) - 1})"

        if self._alerta is not None:
            try:
                self._alerta.close()
            except RuntimeError:
                pass

        self._alerta = _AlertaNotificacao(
            titulo, mais_nova["corpo"], self._abrir_notificacoes
        )
        self._alerta.mostrar()
        _tocar_som()

    def _atualizar_badge(self):

        total = self._total_aprovacoes + self._total_nao_lidas

        if total:
            self._badge_aprovacoes.setText(str(total) if total <= 9 else "9+")
            self._badge_aprovacoes.show()
        else:
            self._badge_aprovacoes.hide()

    def _abrir_notificacoes(self):

        try:
            notificacoes = notificacao_service.listar(limit=30)
        except Exception:
            notificacoes = None

        pendentes = []
        if self._admin:
            try:
                pendentes = listar_pendentes()
            except Exception:
                pendentes = None

        self._popover_notificacoes = _Central(self, notificacoes, pendentes)
        self._popover_notificacoes.abrir_sob(self.bt_notificacoes)

    def _marcar_todas_notificacoes_lidas(self):

        try:
            notificacao_service.marcar_todas_lidas()
        except Exception:
            return

        self._atualizar_contagem_notificacoes()

        if self._popover_notificacoes is not None:
            self._popover_notificacoes.marcar_todas_lidas()

    def _ao_resolver_aprovacao(self, cartao):
        """Chamado por um _CartaoAprovacao depois de aprovar/rejeitar
        com sucesso -- tira o card do popover e atualiza o badge."""

        cartao.setParent(None)
        cartao.deleteLater()

        self._atualizar_contagem_aprovacoes()

    def _abrir_menu_perfil(self):

        popover = _Popover(largura=230)

        if self._na_barra:
            quem = QLabel(f"<b>{self._nome_usuario}</b><br>{self._cargo}")
            quem.setStyleSheet(
                f"background:transparent; border:none; color:{tokens.TEXTO}; "
                f"font-size:{tokens.TAMANHO_SM}px; padding:8px 10px;"
            )
            popover.layout_corpo.addWidget(quem)
            item_tema = _ItemMenu(
                "Tema claro" if self._modo_escuro else "Tema escuro",
                icone_nome="sun" if self._modo_escuro else "moon",
            )
            item_tema.clicked.connect(popover.close)
            item_tema.clicked.connect(self._alternar_tema)
            popover.layout_corpo.addWidget(item_tema)

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
