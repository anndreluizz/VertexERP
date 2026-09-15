import math
import os
import sys

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer, QVariantAnimation
from PySide6.QtGui import QColor, QCursor, QLinearGradient, QPainter, QRadialGradient
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
    QGraphicsDropShadowEffect,
)

from requests.exceptions import ConnectionError

from design import tokens
from design.animations import fade_in, slide_up
from design.icons import icone, icone_pixmap
from design.widgets import BotaoPrimario, BotaoSecundario, Card
from services.api import login
from services.preferencias_service import carregar_tema_escuro, salvar_tema_escuro
from telas.verificar_2fa import Verificar2FADialog
from telas.principal import PrincipalWindow


BENEFICIOS = [
    ("shopping-cart", "Vendas", "Mais agilidade no seu dia a dia"),
    ("package", "Estoque", "Controle total dos produtos"),
    ("users", "Clientes", "Relacionamento mais forte"),
    ("wallet", "Financeiro", "Decisões com mais segurança"),
]


class _PainelAnimado(QFrame):
    """Painel de marca com um gradiente que "respira" bem devagar e
    formas suaves flutuando ao fundo -- só decoração (roda por baixo
    dos widgets de conteúdo, que continuam layoutados normalmente por
    cima via QVBoxLayout, sem saber que o fundo é animado). Pensado
    pra dar uma sensação de profundidade/movimento discreta, sem virar
    distração numa tela de login de um sistema de gestão."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._fase = 0.0

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(11000)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setLoopCount(-1)
        self._anim.valueChanged.connect(self._ao_animar)
        self._anim.start()

    def parar_animacao(self):
        self._anim.stop()

    def _ao_animar(self, valor):
        self._fase = float(valor)
        self.update()

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        largura = self.width()
        altura = self.height()

        # gradiente principal -- o ponto final oscila bem devagar num
        # raio pequeno, dando a impressão de um gradiente "vivo" sem
        # trocar de cor de verdade (continua reconhecivelmente azul)
        onda = math.sin(self._fase * 2 * math.pi)
        x2 = largura * (0.85 + onda * 0.15)
        y2 = altura * (0.85 - onda * 0.1)

        gradiente = QLinearGradient(0, 0, x2, y2)
        gradiente.setColorAt(0, QColor(tokens.PRIMARIA))
        gradiente.setColorAt(1, QColor(tokens.PRIMARIA_ESCURA))

        painter.fillRect(self.rect(), gradiente)

        self._desenhar_forma(painter, largura * 0.88, altura * 0.1, 150, 0.0)
        self._desenhar_forma(painter, largura * 0.06, altura * 0.55, 170, 0.33)
        self._desenhar_forma(painter, largura * 0.8, altura * 0.92, 130, 0.66)

    def _desenhar_forma(self, painter, x_base, y_base, raio, deslocamento_fase):
        """Um círculo com borda suave (gradiente radial que desaparece
        pra transparente) balançando devagar em volta de um ponto --
        dá profundidade sem competir com o texto por cima."""

        fase_local = (self._fase + deslocamento_fase) % 1.0
        deslocamento = math.sin(fase_local * 2 * math.pi) * 20

        gradiente = QRadialGradient(x_base, y_base + deslocamento, raio)
        gradiente.setColorAt(0.0, QColor(255, 255, 255, 22))
        gradiente.setColorAt(1.0, QColor(255, 255, 255, 0))

        painter.setPen(Qt.NoPen)
        painter.setBrush(gradiente)
        painter.drawEllipse(QPointF(x_base, y_base + deslocamento), raio, raio)


class _IlustracaoPainel(QWidget):
    """Ilustração 2D simples (uma "prévia" do painel do sistema, com
    duas etiquetas flutuando por cima) no lugar de uma arte 3D de
    verdade -- que não dá pra desenhar com QPainter/QWidget. Fica
    plana/flat de propósito, sem tentar imitar realismo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(300, 176)
        self.setStyleSheet("background:transparent;")

        mockup = self._construir_mockup()
        mockup.setGeometry(18, 24, 264, 138)

        selo_vendas = self._construir_selo("shopping-cart")
        selo_vendas.setGeometry(0, 4, 56, 56)

        selo_grafico = self._construir_selo("trending-up")
        selo_grafico.setGeometry(238, 116, 56, 56)

    def _construir_mockup(self):

        card = Card(parent=self, elevado=True)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        topo = QHBoxLayout()
        topo.setSpacing(6)
        for cor in ("#FF5F57", "#FEBC2E", "#28C840"):
            ponto = QLabel()
            ponto.setFixedSize(9, 9)
            ponto.setStyleSheet(f"background:{cor}; border-radius:4px;")
            topo.addWidget(ponto)
        topo.addStretch()
        layout.addLayout(topo)

        linha_stats = QHBoxLayout()
        linha_stats.setSpacing(8)
        for largura in (64, 44):
            barra = QLabel()
            barra.setFixedSize(largura, 8)
            barra.setStyleSheet(f"background:{tokens.FUNDO}; border-radius:4px;")
            linha_stats.addWidget(barra)
        linha_stats.addStretch()
        layout.addLayout(linha_stats)

        barras = QHBoxLayout()
        barras.setSpacing(7)
        barras.setAlignment(Qt.AlignBottom)
        for altura, opaco in ((22, False), (38, True), (28, False), (48, True), (34, False)):
            barra = QLabel()
            barra.setFixedWidth(20)
            barra.setFixedHeight(altura)
            cor = tokens.PRIMARIA if opaco else tokens.BORDA_FORTE
            barra.setStyleSheet(f"background:{cor}; border-radius:4px;")
            barras.addWidget(barra)
        barras.addStretch()
        layout.addLayout(barras)

        return card

    def _construir_selo(self, icone_nome):

        selo = QFrame(self)
        selo.setStyleSheet("""
            QFrame {
                background: rgba(255, 255, 255, 0.18);
                border: 1px solid rgba(255, 255, 255, 0.3);
                border-radius: 16px;
            }
        """)

        sombra = QGraphicsDropShadowEffect(selo)
        sombra.setBlurRadius(24)
        sombra.setOffset(0, 8)
        sombra.setColor(QColor(0, 0, 0, 70))
        selo.setGraphicsEffect(sombra)

        layout = QVBoxLayout(selo)
        layout.setContentsMargins(0, 0, 0, 0)

        icone_lbl = QLabel()
        icone_lbl.setAlignment(Qt.AlignCenter)
        icone_lbl.setStyleSheet("background:transparent; border:none;")
        icone_lbl.setPixmap(icone_pixmap(icone_nome, cor=tokens.TEXTO_CLARO, tamanho=22))

        layout.addWidget(icone_lbl)

        return selo


class LoginWindow(QWidget):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Vertex ERP")
        self.resize(1180, 720)
        self.setMinimumSize(1000, 680)
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._painel_marca = self._construir_painel_marca()

        layout.addWidget(self._painel_marca, stretch=5)
        layout.addWidget(self._construir_painel_formulario(), stretch=6)

        self.usuario.setFocus()

        fade_in(self, duracao=260)
        self._animar_beneficios_escalonado()

    def closeEvent(self, event):
        # getattr defensivo: em testes a janela pode ser criada via
        # __new__ (pulando o __init__), sem _painel_marca nenhum
        painel = getattr(self, "_painel_marca", None)
        if painel is not None:
            painel.parar_animacao()
        super().closeEvent(event)

    # ======================================
    # PAINEL ESQUERDO — MARCA
    # ======================================

    def _construir_painel_marca(self):

        painel = _PainelAnimado()

        layout = QVBoxLayout(painel)
        layout.setContentsMargins(52, 48, 52, 40)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignVCenter)

        marca = QLabel("V")
        marca.setFixedSize(52, 52)
        marca.setAlignment(Qt.AlignCenter)
        marca.setStyleSheet("""
            background: rgba(255, 255, 255, 0.16);
            color: white;
            border-radius: 15px;
            font-size: 24px;
            font-weight: 800;
        """)
        layout.addWidget(marca)
        layout.addSpacing(20)

        titulo = QLabel("Vertex ERP")
        titulo.setStyleSheet("""
            background:transparent; color:white;
            font-size:29px; font-weight:800;
        """)
        layout.addWidget(titulo)
        layout.addSpacing(4)

        tagline = QLabel("G E S T Ã O   S E M   L I M I T E S")
        tagline.setStyleSheet("""
            background:transparent; color: rgba(255, 255, 255, 0.6);
            font-size:11px; font-weight:700;
        """)
        layout.addWidget(tagline)
        layout.addSpacing(18)

        descricao = QLabel(
            "A gestão completa da sua loja: vendas, estoque, clientes\n"
            "e financeiro, em um sistema só — rápido e sem complicação."
        )
        descricao.setWordWrap(True)
        descricao.setStyleSheet("""
            background:transparent; color: rgba(255, 255, 255, 0.82);
            font-size:13px; line-height: 1.5;
        """)
        layout.addWidget(descricao)
        layout.addSpacing(26)

        self._linhas_beneficio = []

        for icone_nome, titulo_beneficio, subtitulo in BENEFICIOS:
            linha = self._linha_beneficio(icone_nome, titulo_beneficio, subtitulo)
            self._linhas_beneficio.append(linha)
            layout.addWidget(linha)
            layout.addSpacing(10)

        layout.addSpacing(16)
        layout.addWidget(_IlustracaoPainel(), alignment=Qt.AlignLeft)

        layout.addStretch()

        return painel

    def _animar_beneficios_escalonado(self):
        """Entram um de cada vez (em vez de todos de uma vez com o
        resto da tela) -- reaproveita fade_in/slide_up já existentes,
        só com um atrasinho crescente entre eles."""

        for indice, linha in enumerate(self._linhas_beneficio):
            atraso = 240 + indice * 100
            QTimer.singleShot(
                atraso,
                lambda linha=linha: (fade_in(linha, duracao=300), slide_up(linha, duracao=300)),
            )

    def _linha_beneficio(self, icone_nome, titulo, subtitulo):

        linha = QWidget()
        linha.setStyleSheet("background:transparent;")

        linha_layout = QHBoxLayout(linha)
        linha_layout.setContentsMargins(0, 0, 0, 0)
        linha_layout.setSpacing(13)

        bolha = QLabel()
        bolha.setFixedSize(36, 36)
        bolha.setAlignment(Qt.AlignCenter)
        bolha.setStyleSheet("""
            background: rgba(255, 255, 255, 0.16);
            border-radius: 11px;
        """)
        bolha.setPixmap(icone_pixmap(icone_nome, cor=tokens.TEXTO_CLARO, tamanho=17))

        coluna = QVBoxLayout()
        coluna.setSpacing(1)
        coluna.setContentsMargins(0, 0, 0, 0)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color: {tokens.TEXTO_CLARO};
            font-size:13.5px; font-weight:700;
        """)

        lbl_subtitulo = QLabel(subtitulo)
        lbl_subtitulo.setWordWrap(True)
        lbl_subtitulo.setStyleSheet("""
            background:transparent; color: rgba(255, 255, 255, 0.72);
            font-size:11.5px;
        """)

        coluna.addWidget(lbl_titulo)
        coluna.addWidget(lbl_subtitulo)

        linha_layout.addWidget(bolha)
        linha_layout.addLayout(coluna, stretch=1)

        return linha

    # ======================================
    # PAINEL DIREITO — FORMULÁRIO
    # ======================================

    def _construir_painel_formulario(self):

        painel = QFrame()
        painel.setStyleSheet(f"background:{tokens.FUNDO};")

        externo = QVBoxLayout(painel)
        externo.setContentsMargins(28, 20, 28, 24)
        externo.setSpacing(0)

        barra_topo = QHBoxLayout()
        barra_topo.addStretch()
        barra_topo.addWidget(self._construir_bt_tema())
        externo.addLayout(barra_topo)

        externo.addStretch()

        cartao = Card(elevado=True)
        cartao.setFixedWidth(400)

        layout = QVBoxLayout(cartao)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(4)

        titulo_row = QHBoxLayout()
        titulo_row.setSpacing(12)

        titulo_coluna = QVBoxLayout()
        titulo_coluna.setSpacing(4)

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

        titulo_coluna.addWidget(titulo)
        titulo_coluna.addWidget(subtitulo)

        marca_pequena = QLabel("V")
        marca_pequena.setFixedSize(40, 40)
        marca_pequena.setAlignment(Qt.AlignCenter)
        marca_pequena.setStyleSheet(f"""
            background: {tokens.PRIMARIA};
            color: white;
            border-radius: 12px;
            font-size: 17px;
            font-weight: 800;
        """)

        titulo_row.addLayout(titulo_coluna, stretch=1)
        titulo_row.addWidget(marca_pequena, alignment=Qt.AlignTop)

        layout.addLayout(titulo_row)
        layout.addSpacing(28)

        lbl_email = QLabel("E-MAIL")
        lbl_email.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        layout.addWidget(lbl_email)
        layout.addSpacing(6)
        layout.addWidget(self._construir_campo_email())
        layout.addSpacing(16)

        lbl_senha = QLabel("SENHA")
        lbl_senha.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        layout.addWidget(lbl_senha)
        layout.addSpacing(6)
        layout.addWidget(self._construir_campo_senha())
        layout.addSpacing(12)

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
        layout.addSpacing(20)

        self.botao = BotaoPrimario("Entrar")
        self.botao.setMinimumHeight(46)
        self.botao.clicked.connect(self.entrar)

        layout.addWidget(self.botao)
        layout.addSpacing(18)
        layout.addWidget(self._construir_divisor())
        layout.addSpacing(18)

        bt_cadastrar = BotaoSecundario("Cadastre-se", icone_nome="users")
        bt_cadastrar.setMinimumHeight(44)
        bt_cadastrar.clicked.connect(self.ir_para_cadastro)
        layout.addWidget(bt_cadastrar)
        layout.addSpacing(14)

        bt_config_servidor = QPushButton("Configurar servidor")
        bt_config_servidor.setCursor(Qt.PointingHandCursor)
        bt_config_servidor.setAutoDefault(False)
        bt_config_servidor.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_XS}px;
            }}
            QPushButton:hover {{ color:{tokens.TEXTO_SECUNDARIO}; }}
        """)
        bt_config_servidor.clicked.connect(self.configurar_servidor)

        layout.addWidget(bt_config_servidor, alignment=Qt.AlignCenter)

        externo.addWidget(cartao, alignment=Qt.AlignHCenter)
        externo.addSpacing(24)
        externo.addWidget(self._construir_selos_confianca())

        externo.addStretch()

        return painel

    def _construir_divisor(self):

        divisor = QWidget()
        divisor.setStyleSheet("background:transparent;")

        divisor_layout = QHBoxLayout(divisor)
        divisor_layout.setContentsMargins(0, 0, 0, 0)
        divisor_layout.setSpacing(10)

        linha_esq = QFrame()
        linha_esq.setFixedHeight(1)
        linha_esq.setStyleSheet(f"background:{tokens.BORDA}; border:none;")

        lbl_ou = QLabel("ou")
        lbl_ou.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        linha_dir = QFrame()
        linha_dir.setFixedHeight(1)
        linha_dir.setStyleSheet(f"background:{tokens.BORDA}; border:none;")

        divisor_layout.addWidget(linha_esq, stretch=1)
        divisor_layout.addWidget(lbl_ou)
        divisor_layout.addWidget(linha_dir, stretch=1)

        return divisor

    def _construir_selos_confianca(self):

        linha = QWidget()
        linha.setStyleSheet("background:transparent;")

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)

        selos = (
            ("lock", "Seus dados", "sempre protegidos"),
            ("refresh-cw", "Sistema sempre", "atualizado"),
            ("message-circle", "Suporte quando", "você precisar"),
        )

        for icone_nome, linha1, linha2 in selos:
            layout.addWidget(self._selo_confianca(icone_nome, linha1, linha2), stretch=1)

        return linha

    def _selo_confianca(self, icone_nome, linha1, linha2):

        selo = QWidget()
        selo.setStyleSheet("background:transparent;")

        layout = QHBoxLayout(selo)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)

        icone_lbl = QLabel()
        icone_lbl.setPixmap(icone_pixmap(icone_nome, cor=tokens.TEXTO_TERCIARIO, tamanho=15))
        icone_lbl.setStyleSheet("background:transparent;")

        texto = QLabel(f"{linha1}\n{linha2}")
        texto.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:10.5px; line-height:1.3;
        """)

        layout.addWidget(icone_lbl, alignment=Qt.AlignTop)
        layout.addWidget(texto)

        return selo

    def _construir_bt_tema(self):

        escuro_atual = carregar_tema_escuro()
        texto = "  Tema escuro" if not escuro_atual else "  Tema claro"
        nome_icone = "moon" if not escuro_atual else "sun"

        bt = QPushButton(texto)
        bt.setIcon(icone(nome_icone, cor=tokens.TEXTO_SECUNDARIO, tamanho=15))
        bt.setCursor(Qt.PointingHandCursor)
        bt.setAutoDefault(False)
        bt.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.TEXTO_SECUNDARIO}; font-size:{tokens.TAMANHO_SM}px;
                padding: 6px 8px;
            }}
            QPushButton:hover {{ color:{tokens.TEXTO}; }}
        """)
        bt.clicked.connect(self._alternar_tema)

        return bt

    def _alternar_tema(self):

        escuro_novo = not carregar_tema_escuro()
        salvar_tema_escuro(escuro_novo)

        resposta = QMessageBox.question(
            self,
            "Reiniciar o Vertex ERP",
            "O tema só é aplicado depois de reiniciar o programa.\n\n"
            "Reiniciar agora?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if resposta == QMessageBox.Yes:
            self._reiniciar_app()

    def _reiniciar_app(self):

        QApplication.instance().quit()

        # os.execv troca o processo atual pelo mesmo comando de novo --
        # forma padrao de "reiniciar" um app Python sem depender de um
        # processo externo pra relancar (mesma logica de
        # telas/principal.py:_reiniciar_app)
        if getattr(sys, "frozen", False):
            comando = [sys.executable] + sys.argv[1:]
        else:
            comando = [sys.executable, sys.argv[0]] + sys.argv[1:]

        os.execv(sys.executable, comando)

    def _construir_campo_email(self):

        campo_email = QFrame()
        self._estilizar_campo(campo_email, focado=False)
        campo_email_layout = QHBoxLayout(campo_email)
        campo_email_layout.setContentsMargins(14, 0, 14, 0)
        campo_email_layout.setSpacing(8)

        icone_lbl = QLabel()
        icone_lbl.setPixmap(icone_pixmap("mail", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        icone_lbl.setStyleSheet("background:transparent;")

        self.usuario = QLineEdit()
        self.usuario.setPlaceholderText("seu@contato.com")
        self.usuario.setMinimumHeight(44)
        self.usuario.setStyleSheet(f"""
            QLineEdit {{
                background:transparent; border:none;
                font-size:{tokens.TAMANHO_MD}px; color:{tokens.TEXTO};
            }}
        """)
        self.usuario.installEventFilter(self)
        self._campo_email_frame = campo_email

        campo_email_layout.addWidget(icone_lbl)
        campo_email_layout.addWidget(self.usuario)

        return campo_email

    def _construir_campo_senha(self):

        campo_senha = QFrame()
        self._estilizar_campo(campo_senha, focado=False)
        campo_senha_layout = QHBoxLayout(campo_senha)
        campo_senha_layout.setContentsMargins(14, 0, 8, 0)
        campo_senha_layout.setSpacing(8)

        icone_lbl = QLabel()
        icone_lbl.setPixmap(icone_pixmap("lock", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        icone_lbl.setStyleSheet("background:transparent;")

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

        campo_senha_layout.addWidget(icone_lbl)
        campo_senha_layout.addWidget(self.senha)
        campo_senha_layout.addWidget(self.bt_ver_senha)

        return campo_senha

    def _estilizar_campo(self, campo_frame, focado):

        cor_borda = tokens.PRIMARIA if focado else tokens.BORDA

        campo_frame.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border: 1.5px solid {cor_borda};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

    def eventFilter(self, observado, evento):

        # getattr defensivo: o campo de e-mail e' montado antes do de
        # senha, entao um evento que chegue nesse meio-tempo veria
        # self.senha ainda inexistente
        if observado is getattr(self, "senha", None):
            if evento.type() == QEvent.FocusIn:
                self._estilizar_campo(self._campo_senha_frame, focado=True)
            elif evento.type() == QEvent.FocusOut:
                self._estilizar_campo(self._campo_senha_frame, focado=False)

        elif observado is getattr(self, "usuario", None):
            if evento.type() == QEvent.FocusIn:
                self._estilizar_campo(self._campo_email_frame, focado=True)
            elif evento.type() == QEvent.FocusOut:
                self._estilizar_campo(self._campo_email_frame, focado=False)

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

    def configurar_servidor(self):

        from telas.conectar_servidor import ConectarServidorDialog

        dialogo = ConectarServidorDialog(parent=self)
        dialogo.exec()

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

            ok, erro, verificacao_id = login(
                self.usuario.text().strip(),
                self.senha.text(),
                lembrar=self.manter_conectado.isChecked(),
            )

            QApplication.restoreOverrideCursor()

            if ok:

                self.principal = PrincipalWindow()
                self.principal.show()
                self.close()

            elif verificacao_id:

                # senha certa, mas falta o segundo fator (2FA) -- o
                # codigo ja foi mandado por e-mail nesse momento (ver
                # services/api.py: login())
                dialogo = Verificar2FADialog(
                    verificacao_id,
                    self.usuario.text().strip(),
                    lembrar=self.manter_conectado.isChecked(),
                    parent=self,
                )

                if dialogo.exec() == Verificar2FADialog.Accepted:
                    self.principal = PrincipalWindow()
                    self.principal.show()
                    self.close()

            else:

                QMessageBox.warning(
                    self,
                    "Erro",
                    erro,
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
