import math
import os
import sys
import tempfile
from datetime import datetime

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
    QGridLayout,
    QFrame,
    QMessageBox,
    QApplication,
)

from requests.exceptions import ConnectionError

from design import tokens
from design.animations import fade_in, slide_up
from design.icons import icone, icone_pixmap
from design.widgets import BotaoPrimario
from services import api
from services.api import login, me, configuracoes
from services.preferencias_service import carregar_tema_escuro, salvar_tema_escuro
from services.worker import rodar_em_thread, em_paralelo
from utils.acessibilidade import movimento_reduzido
from telas.verificar_2fa import Verificar2FADialog
from telas.principal import PrincipalWindow


BENEFICIOS = [
    ("shopping-cart", "Vendas", "Caixa rápido no balcão"),
    ("package", "Estoque", "Produto certo na prateleira"),
    ("users", "Clientes", "Fiado sem caderninho"),
    ("wallet", "Financeiro", "Contas sempre em dia"),
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

        # decorativa e roda pra sempre (loop infinito) -- com "Mostrar
        # animacoes" desligado no Windows, nem comeca (fica parada na
        # fase inicial, ainda com o gradiente estatico de paintEvent)
        if not movimento_reduzido():
            self._anim.start()

    def parar_animacao(self):
        self._anim.stop()

    def _ao_animar(self, valor):
        # mesmo caso de widgets/nav_card.py::_ao_animar_sombra e
        # design/widgets.py::_BotaoAnimado._ao_animar: stop() chamado
        # antes da animacao ter rodado alguma vez (ou no meio do loop
        # infinito, ao trocar de tela apos o login) pode emitir
        # valueChanged(None) -- sem essa guarda, float(None) estoura
        # TypeError e derruba o processo bem na transicao pro sistema.
        if valor is None:
            return

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


def _saudacao():
    hora = datetime.now().hour
    if hora < 12:
        return "Bom dia"
    if hora < 18:
        return "Boa tarde"
    return "Boa noite"


def _icone_check_arquivo():
    """O ::indicator:checked do QCheckBox só aceita imagem por caminho
    de arquivo (não QPixmap) -- grava o ícone 'check' branco uma vez
    numa pasta temporária e devolve o caminho com barras '/', que é o
    que o url() do stylesheet do Qt espera mesmo no Windows."""

    caminho = os.path.join(tempfile.gettempdir(), "vertexerp_check_branco.png")
    if not os.path.exists(caminho):
        icone_pixmap("check", cor="#FFFFFF", tamanho=14).save(caminho, "PNG")
    return caminho.replace("\\", "/")


def _buscar_info_principal():
    """Roda na worker thread -- me()+configuracoes() que
    PrincipalWindow precisa pra se montar (Header/Sidebar), buscados
    ANTES de construir a janela em vez de dentro do __init__ dela (ver
    telas/principal.py) -- assim a janela nao trava a GUI thread
    esperando essas 2 chamadas. As duas sao independentes, entao
    disparam em paralelo (ver services/worker.py::em_paralelo)."""
    return em_paralelo((me,), (configuracoes,))


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
        layout.setContentsMargins(56, 44, 56, 36)
        layout.setSpacing(0)

        # ---- logo no topo
        topo = QHBoxLayout()
        topo.setSpacing(12)

        marca = QLabel("V")
        marca.setFixedSize(40, 40)
        marca.setAlignment(Qt.AlignCenter)
        marca.setStyleSheet("""
            background: rgba(255, 255, 255, 0.16);
            color: white; border-radius: 12px;
            font-size: 19px; font-weight: 800;
        """)

        nome = QLabel("Vertex ERP")
        nome.setStyleSheet("""
            background:transparent; color:white;
            font-size:18px; font-weight:800;
        """)

        topo.addWidget(marca)
        topo.addWidget(nome)
        topo.addStretch()
        layout.addLayout(topo)

        layout.addStretch(3)

        # ---- mensagem principal
        titulo = QLabel("Sua loja organizada,\ndo caixa ao fiado.")
        titulo.setStyleSheet("""
            background:transparent; color:white;
            font-size:34px; font-weight:800;
        """)
        layout.addWidget(titulo)
        layout.addSpacing(14)

        descricao = QLabel(
            "Vendas, estoque, clientes e financeiro num lugar só, "
            "pra você fechar o dia sabendo exatamente onde está cada real."
        )
        descricao.setWordWrap(True)
        descricao.setMaximumWidth(440)
        descricao.setStyleSheet("""
            background:transparent; color: rgba(255, 255, 255, 0.80);
            font-size:14px;
        """)
        layout.addWidget(descricao)
        layout.addSpacing(36)

        # ---- benefícios, um por linha (em 2 colunas o texto quebrava
        # na largura mínima da janela)
        grade = QGridLayout()
        grade.setVerticalSpacing(16)

        self._linhas_beneficio = []

        for indice, (icone_nome, titulo_beneficio, subtitulo) in enumerate(BENEFICIOS):
            linha = self._linha_beneficio(icone_nome, titulo_beneficio, subtitulo)
            self._linhas_beneficio.append(linha)
            grade.addWidget(linha, indice, 0)

        layout.addLayout(grade)

        layout.addStretch(4)

        # ---- rodapé: em qual servidor este PC vai entrar (ajuda a
        # perceber na hora um Terminal apontando pro lugar errado)
        endereco = api.URL.split("://", 1)[-1]
        rodape = QLabel(f"●  Servidor: {endereco}")
        rodape.setStyleSheet("""
            background:transparent; color: rgba(255, 255, 255, 0.55);
            font-size:12px;
        """)
        layout.addWidget(rodape)

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
        linha_layout.setSpacing(12)

        bolha = QLabel()
        bolha.setFixedSize(36, 36)
        bolha.setAlignment(Qt.AlignCenter)
        bolha.setStyleSheet("""
            background: rgba(255, 255, 255, 0.12);
            border-radius: 10px;
        """)
        bolha.setPixmap(icone_pixmap(icone_nome, cor=tokens.TEXTO_CLARO, tamanho=17))

        coluna = QVBoxLayout()
        coluna.setSpacing(1)
        coluna.setContentsMargins(0, 0, 0, 0)

        lbl_titulo = QLabel(titulo)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color: {tokens.TEXTO_CLARO};
            font-size:14px; font-weight:700;
        """)

        lbl_subtitulo = QLabel(subtitulo)
        lbl_subtitulo.setWordWrap(True)
        lbl_subtitulo.setStyleSheet("""
            background:transparent; color: rgba(255, 255, 255, 0.70);
            font-size:12px;
        """)

        coluna.addWidget(lbl_titulo)
        coluna.addWidget(lbl_subtitulo)

        linha_layout.addWidget(bolha, alignment=Qt.AlignTop)
        linha_layout.addLayout(coluna, stretch=1)

        return linha

    # ======================================
    # PAINEL DIREITO — FORMULÁRIO
    # ======================================

    def _construir_painel_formulario(self):

        painel = QFrame()
        painel.setStyleSheet(f"background:{tokens.CARD};")

        externo = QVBoxLayout(painel)
        externo.setContentsMargins(28, 20, 28, 24)
        externo.setSpacing(0)

        barra_topo = QHBoxLayout()
        barra_topo.addStretch()
        barra_topo.addWidget(self._construir_bt_tema())
        externo.addLayout(barra_topo)

        externo.addStretch(2)

        # formulário "solto" no painel (sem cartão em volta): o painel
        # da direita inteiro já é a superfície do formulário
        coluna = QWidget()
        coluna.setFixedWidth(372)
        coluna.setStyleSheet("background:transparent;")

        layout = QVBoxLayout(coluna)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        saudacao = QLabel(_saudacao().upper())
        saudacao.setStyleSheet(f"""
            background:transparent; color:{tokens.PRIMARIA};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800;
            letter-spacing: 1px;
        """)
        layout.addWidget(saudacao)
        layout.addSpacing(8)

        titulo = QLabel("Entrar no Vertex")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XXL}px; font-weight:800;
        """)
        layout.addWidget(titulo)
        layout.addSpacing(6)

        subtitulo = QLabel("Use o e-mail e a senha cadastrados na loja.")
        subtitulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_MD}px;
        """)
        layout.addWidget(subtitulo)
        layout.addSpacing(32)

        layout.addWidget(self._rotulo_campo("E-mail"))
        layout.addSpacing(8)
        layout.addWidget(self._construir_campo_email())
        layout.addSpacing(18)

        layout.addWidget(self._rotulo_campo("Senha"))
        layout.addSpacing(8)
        layout.addWidget(self._construir_campo_senha())
        layout.addSpacing(16)

        linha_opcoes = QHBoxLayout()

        self.manter_conectado = QCheckBox("Manter conectado")
        self.manter_conectado.setChecked(True)
        self.manter_conectado.setCursor(Qt.PointingHandCursor)
        self.manter_conectado.setStyleSheet(f"""
            QCheckBox {{
                background:transparent; color:{tokens.TEXTO_SECUNDARIO};
                font-size:{tokens.TAMANHO_BASE}px; spacing: 8px;
            }}
            QCheckBox::indicator {{
                width: 18px; height: 18px;
                border-radius: 5px;
                border: 1.5px solid {tokens.BORDA_FORTE};
                background: {tokens.CARD};
            }}
            QCheckBox::indicator:checked {{
                border: 1.5px solid {tokens.PRIMARIA};
                background: {tokens.PRIMARIA};
                image: url("{_icone_check_arquivo()}");
            }}
        """)

        bt_esqueceu = self._link("Esqueceu a senha?", tokens.PRIMARIA, tokens.PRIMARIA_HOVER)
        bt_esqueceu.clicked.connect(self.esqueceu_senha)

        linha_opcoes.addWidget(self.manter_conectado)
        linha_opcoes.addStretch()
        linha_opcoes.addWidget(bt_esqueceu)

        layout.addLayout(linha_opcoes)
        layout.addSpacing(24)

        self.botao = BotaoPrimario("Entrar")
        self.botao.setMinimumHeight(48)
        self.botao.clicked.connect(self.entrar)

        layout.addWidget(self.botao)
        layout.addSpacing(22)

        linha_cadastro = QHBoxLayout()
        linha_cadastro.setSpacing(4)
        linha_cadastro.addStretch()
        lbl_primeira = QLabel("Primeira vez aqui?")
        lbl_primeira.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_BASE}px;
        """)
        bt_cadastrar = self._link("Cadastrar a loja", tokens.PRIMARIA, tokens.PRIMARIA_HOVER)
        bt_cadastrar.clicked.connect(self.ir_para_cadastro)
        linha_cadastro.addWidget(lbl_primeira)
        linha_cadastro.addWidget(bt_cadastrar)
        linha_cadastro.addStretch()
        layout.addLayout(linha_cadastro)

        externo.addWidget(coluna, alignment=Qt.AlignHCenter)

        externo.addStretch(3)

        bt_config_servidor = self._link(
            "Configurar servidor", tokens.TEXTO_TERCIARIO, tokens.TEXTO_SECUNDARIO,
            tamanho=tokens.TAMANHO_SM, peso=500,
        )
        bt_config_servidor.setIcon(icone("settings", cor=tokens.TEXTO_TERCIARIO, tamanho=14))
        bt_config_servidor.clicked.connect(self.configurar_servidor)
        externo.addWidget(bt_config_servidor, alignment=Qt.AlignHCenter)

        return painel

    def _rotulo_campo(self, texto):

        lbl = QLabel(texto)
        lbl.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_BASE}px; font-weight:600;
        """)
        return lbl

    def _link(self, texto, cor, cor_hover, tamanho=None, peso=700):

        bt = QPushButton(texto)
        bt.setCursor(Qt.PointingHandCursor)
        bt.setAutoDefault(False)
        bt.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; padding:2px 0;
                color:{cor}; font-size:{tamanho or tokens.TAMANHO_BASE}px;
                font-weight:{peso};
            }}
            QPushButton:hover {{ color:{cor_hover}; text-decoration: underline; }}
        """)
        return bt

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
        self.usuario.setPlaceholderText("voce@sualoja.com.br")
        self.usuario.setMinimumHeight(46)
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
        self.senha.setMinimumHeight(46)
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
        self.bt_ver_senha.setToolTip("Mostrar senha")
        self.bt_ver_senha.setAccessibleName("Mostrar senha")
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

        # seletor por objectName (e não "QFrame"): QLabel herda de
        # QFrame, então "QFrame { border... }" desenhava uma caixinha
        # com borda em volta do ícone de e-mail/cadeado dentro do campo
        campo_frame.setObjectName("CampoLogin")
        campo_frame.setStyleSheet(f"""
            #CampoLogin {{
                background: {tokens.CARD if focado else tokens.FUNDO};
                border: 1.5px solid {cor_borda};
                border-radius: {tokens.RADIUS_MD}px;
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
            self.bt_ver_senha.setToolTip("Ocultar senha")
            self.bt_ver_senha.setAccessibleName("Ocultar senha")
        else:
            self.senha.setEchoMode(QLineEdit.Password)
            self.bt_ver_senha.setIcon(
                icone("eye", cor=tokens.TEXTO_TERCIARIO, tamanho=18)
            )
            self.bt_ver_senha.setToolTip("Mostrar senha")
            self.bt_ver_senha.setAccessibleName("Mostrar senha")

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

        if not self.botao.isEnabled():
            # ja tem um login em andamento -- clique duplo (ou Enter
            # depois de clicar) so' faria bater no backend duas vezes.
            # Antes disso ser desnecessario: a chamada sincrona
            # travava a janela inteira, entao um segundo clique era
            # fisicamente impossivel de acontecer no meio; assincrono,
            # vira possivel de verdade.
            return

        self._definir_entrando(True)

        rodar_em_thread(
            self,
            login,
            self.usuario.text().strip(),
            self.senha.text(),
            lembrar=self.manter_conectado.isChecked(),
            ao_sucesso=self._ao_login_sucesso,
            ao_erro=self._ao_login_erro,
            ao_finalizar=self._ao_login_finalizado,
        )

    def _ao_login_finalizado(self):
        self._definir_entrando(False)

    def _definir_entrando(self, entrando: bool):

        self.botao.setEnabled(not entrando)
        self.usuario.setEnabled(not entrando)
        self.senha.setEnabled(not entrando)

        if entrando:
            QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()

    def _ao_login_sucesso(self, resultado):

        ok, erro, verificacao_id = resultado

        if ok:

            self._abrir_principal()

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
                self._abrir_principal()

        else:

            QMessageBox.warning(
                self,
                "Erro",
                erro,
            )

    def _abrir_principal(self):

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        rodar_em_thread(
            self,
            _buscar_info_principal,
            ao_sucesso=self._ao_buscar_info_principal_sucesso,
            ao_erro=self._ao_buscar_info_principal_erro,
            ao_finalizar=self._ao_buscar_info_principal_finalizado,
        )

    def _ao_buscar_info_principal_finalizado(self):
        QApplication.restoreOverrideCursor()

    def _ao_buscar_info_principal_erro(self, erro):
        QMessageBox.critical(
            self,
            "Erro",
            f"Login feito, mas não foi possível abrir o sistema.\n{erro}",
        )

    def _ao_buscar_info_principal_sucesso(self, resultado):

        info_usuario, config = resultado

        self.principal = PrincipalWindow(info_usuario, config)
        self.principal.show()
        self.close()

    def _ao_login_erro(self, erro):

        if isinstance(erro, ConnectionError):

            QMessageBox.critical(
                self,
                "Servidor Offline",
                "Não foi possível conectar ao Backend.\n\n"
                "Verifique se o FastAPI está executando.",
            )
            return

        QMessageBox.critical(
            self,
            "Erro",
            str(erro),
        )
