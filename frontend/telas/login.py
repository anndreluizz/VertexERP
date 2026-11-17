import math
import os
import sys
from datetime import datetime

from PySide6.QtCore import QEvent, QPointF, Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QVBoxLayout,
    QHBoxLayout,
    QMessageBox,
    QApplication,
)

from requests.exceptions import ConnectionError

from widgets.dialogs.message_dialog import perguntar
from design import tokens
from design.fonts import familia_titulo
from design.icons import icone
from design.login_visual import BotaoEntrar, Fundo, Onda
from services import api
from services.api import login, me, configuracoes
from services.preferencias_service import carregar_tema_escuro, salvar_tema_escuro
from services.worker import rodar_em_thread, em_paralelo
from utils.acessibilidade import movimento_reduzido
from telas.verificar_2fa import Verificar2FADialog
from telas.principal import PrincipalWindow


def _saudacao():
    hora = datetime.now().hour
    if hora < 12:
        return "Bom dia"
    if hora < 18:
        return "Boa tarde"
    return "Boa noite"


def _primeiro_nome(email):
    """'andre.lopes@loja.com' -> 'Andre' (so pra saudar; vazio se nao der)."""
    nome = (email or "").split("@")[0].replace(".", " ").replace("_", " ").strip().title()
    return nome.split()[0] if len(nome) >= 3 else ""


def _buscar_info_principal():
    """Roda na worker thread -- me()+configuracoes() que
    PrincipalWindow precisa pra se montar (Header/Sidebar), buscados
    ANTES de construir a janela em vez de dentro do __init__ dela (ver
    telas/principal.py) -- assim a janela nao trava a GUI thread
    esperando essas 2 chamadas. As duas sao independentes, entao
    disparam em paralelo (ver services/worker.py::em_paralelo)."""
    return em_paralelo((me,), (configuracoes,))


class LoginWindow(QWidget):
    """Login: painel de marca vivo na esquerda (Fundo), formulario na direita.
    O visual vem de design/login_visual.py; aqui fica so a montagem e a logica."""

    MARGEM = 64

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Vertex ERP")
        self.resize(1180, 720)
        self.setMinimumSize(1000, 680)
        # abre maximizada (ocupando a tela, com a barra de tarefas
        # visivel); ao sair do maximizado volta pro tamanho acima.
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet(f"background:{tokens.CARD};")

        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self._fundo = Fundo()
        raiz.addWidget(self._fundo, 58)

        self._painel = QWidget()
        self._painel.setMinimumWidth(500)
        raiz.addWidget(self._painel, 42)
        self._construir_formulario()

        self._onda = Onda(self)
        self._onda.setGeometry(self.rect())
        self._onda_timer = QTimer(self)
        self._onda_timer.setInterval(16)
        self._onda_timer.timeout.connect(self._andar_onda)
        self._onda_destino = None

        self._tremor_timer = QTimer(self)
        self._tremor_timer.setInterval(16)
        self._tremor_timer.timeout.connect(self._andar_tremor)
        self._tremor_i = 0

        self.usuario.setFocus()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        onda = getattr(self, "_onda", None)
        if onda is not None:
            onda.setGeometry(self.rect())

    def closeEvent(self, event):
        # getattr defensivo: em testes a janela pode ser criada via
        # __new__ (pulando o __init__), sem _fundo nenhum
        fundo = getattr(self, "_fundo", None)
        if fundo is not None:
            fundo.parar_animacao()
        super().closeEvent(event)

    # ======================================
    # FORMULARIO (direita)
    # ======================================

    def _rotulo(self, texto):
        lbl = QLabel(texto)
        lbl.setStyleSheet(
            f"background:transparent;color:{tokens.TEXTO_SECUNDARIO};"
            f"font-size:{tokens.TAMANHO_SM}px;font-weight:700;"
        )
        return lbl

    def _campo(self, placeholder, nome_icone):
        campo = QLineEdit()
        campo.setPlaceholderText(placeholder)
        campo.setFixedHeight(52)
        campo.addAction(icone(nome_icone, tokens.TEXTO_TERCIARIO, 19), QLineEdit.LeadingPosition)
        campo.setStyleSheet(
            f"QLineEdit{{border:1.5px solid {tokens.BORDA_CAMPO};border-radius:{tokens.RADIUS_MD}px;"
            f"padding:0 14px;background:{tokens.CARD};color:{tokens.TEXTO};font-size:{tokens.TAMANHO_MD}px;}}"
            f"QLineEdit:focus{{border:2px solid {tokens.PRIMARIA};}}"
        )
        return campo

    def _link(self, texto, cor, cor_hover, tamanho=None, peso=700):
        bt = QPushButton(texto)
        bt.setCursor(Qt.PointingHandCursor)
        bt.setAutoDefault(False)
        bt.setStyleSheet(
            f"QPushButton{{border:none;background:transparent;padding:2px 0;color:{cor};"
            f"font-size:{tamanho or tokens.TAMANHO_BASE}px;font-weight:{peso};}}"
            f"QPushButton:hover{{color:{cor_hover};text-decoration:underline;}}"
        )
        return bt

    def _construir_formulario(self):
        self._lay = QVBoxLayout(self._painel)
        self._lay.setContentsMargins(self.MARGEM, 0, self.MARGEM, 0)
        self._lay.setSpacing(0)
        lay = self._lay

        topo = QHBoxLayout()
        topo.setContentsMargins(0, 26, 0, 0)
        topo.addStretch()
        topo.addWidget(self._construir_bt_tema())
        lay.addLayout(topo)
        lay.addStretch(3)

        saudacao = QLabel(_saudacao().upper())
        saudacao.setStyleSheet(
            f"background:transparent;color:{tokens.PRIMARIA};font-size:{tokens.TAMANHO_XS}px;"
            f"font-weight:800;letter-spacing:1.5px;"
        )
        lay.addWidget(saudacao)
        lay.addSpacing(8)

        self._titulo = QLabel("Entrar no Vertex")
        self._titulo.setStyleSheet(
            f"background:transparent;color:{tokens.TEXTO};font-size:36px;"
            f"font-weight:800;font-family:'{familia_titulo()}';"
        )
        lay.addWidget(self._titulo)
        lay.addSpacing(6)

        self._subtitulo = QLabel("Use o e-mail e a senha cadastrados na loja.")
        self._subtitulo.setStyleSheet(
            f"background:transparent;color:{tokens.TEXTO_SECUNDARIO};font-size:{tokens.TAMANHO_MD}px;"
        )
        lay.addWidget(self._subtitulo)
        lay.addSpacing(30)

        lay.addWidget(self._rotulo("E-mail"))
        lay.addSpacing(8)
        self.usuario = self._campo("voce@sualoja.com.br", "mail")
        lay.addWidget(self.usuario)
        lay.addSpacing(18)

        lay.addWidget(self._rotulo("Senha"))
        lay.addSpacing(8)
        self.senha = self._campo("Sua senha", "lock")
        self.senha.setEchoMode(QLineEdit.Password)
        self._acao_ver = self.senha.addAction(icone("eye", tokens.TEXTO_TERCIARIO, 19), QLineEdit.TrailingPosition)
        self._acao_ver.triggered.connect(self.alternar_ver_senha)
        self.senha.installEventFilter(self)
        lay.addWidget(self.senha)

        # uma linha so' pra avisos (erro de login, Caps Lock): nao pula o layout
        self._aviso = QLabel("")
        self._aviso.setFixedHeight(26)
        self._aviso.setContentsMargins(0, 6, 0, 0)
        self._aviso.setStyleSheet(self._estilo_aviso(tokens.ERRO))
        lay.addWidget(self._aviso)

        opcoes = QHBoxLayout()
        self.manter_conectado = QCheckBox("Manter conectado")
        self.manter_conectado.setChecked(True)
        self.manter_conectado.setCursor(Qt.PointingHandCursor)
        self.manter_conectado.setStyleSheet(
            f"background:transparent;color:{tokens.TEXTO_SECUNDARIO};font-size:{tokens.TAMANHO_SM}px;"
        )
        bt_esqueceu = self._link("Esqueceu a senha?", tokens.PRIMARIA, tokens.PRIMARIA_HOVER, tokens.TAMANHO_SM)
        bt_esqueceu.clicked.connect(self.esqueceu_senha)
        opcoes.addWidget(self.manter_conectado)
        opcoes.addStretch()
        opcoes.addWidget(bt_esqueceu)
        lay.addLayout(opcoes)
        lay.addSpacing(22)

        self.botao = BotaoEntrar()
        self.botao.clicked.connect(self.entrar)
        lay.addWidget(self.botao)
        lay.addSpacing(24)

        primeira = QHBoxLayout()
        primeira.setSpacing(6)
        primeira.addStretch()
        lbl = QLabel("Primeira vez aqui?")
        lbl.setStyleSheet(
            f"background:transparent;color:{tokens.TEXTO_SECUNDARIO};font-size:{tokens.TAMANHO_BASE}px;"
        )
        bt_cadastrar = self._link("Cadastrar minha loja", tokens.PRIMARIA, tokens.PRIMARIA_HOVER)
        bt_cadastrar.clicked.connect(self.ir_para_cadastro)
        primeira.addWidget(lbl)
        primeira.addWidget(bt_cadastrar)
        primeira.addStretch()
        lay.addLayout(primeira)
        lay.addStretch(4)

        rodape = QHBoxLayout()
        rodape.setContentsMargins(0, 0, 0, 22)
        rodape.setSpacing(6)
        endereco = api.URL.split("://", 1)[-1]
        servidor = QLabel(f"Servidor: {endereco}")
        servidor.setStyleSheet(
            f"background:transparent;color:{tokens.TEXTO_TERCIARIO};font-size:{tokens.TAMANHO_XS}px;"
        )
        bt_config = self._link(
            "Configurar servidor", tokens.TEXTO_SECUNDARIO, tokens.TEXTO, tokens.TAMANHO_XS, 600
        )
        bt_config.setIcon(icone("settings", tokens.TEXTO_SECUNDARIO, 14))
        bt_config.clicked.connect(self.configurar_servidor)
        rodape.addWidget(servidor)
        rodape.addStretch()
        rodape.addWidget(bt_config)
        lay.addLayout(rodape)

        self.usuario.textChanged.connect(self._ola)
        self.usuario.returnPressed.connect(self.senha.setFocus)
        self.senha.returnPressed.connect(self.entrar)
        self.senha.textChanged.connect(lambda _: self._limpar_aviso())

    def _estilo_aviso(self, cor):
        return (
            f"background:transparent;color:{cor};font-size:{tokens.TAMANHO_SM}px;font-weight:600;"
        )

    def _construir_bt_tema(self):
        escuro_atual = carregar_tema_escuro()
        bt = QPushButton()
        bt.setFixedSize(40, 40)
        bt.setIcon(icone("sun" if escuro_atual else "moon", tokens.TEXTO_SECUNDARIO, 19))
        bt.setToolTip("Tema claro" if escuro_atual else "Tema escuro")
        bt.setAccessibleName("Alternar tema claro/escuro")
        bt.setCursor(Qt.PointingHandCursor)
        bt.setAutoDefault(False)
        bt.setStyleSheet(
            f"QPushButton{{border:1px solid {tokens.BORDA};border-radius:20px;background:{tokens.CARD};}}"
            f"QPushButton:hover{{background:{tokens.FUNDO};}}"
        )
        bt.clicked.connect(self._alternar_tema)
        return bt

    def _alternar_tema(self):

        escuro_novo = not carregar_tema_escuro()
        salvar_tema_escuro(escuro_novo)

        resposta = perguntar(
            self,
            "Reiniciar o Vertex ERP",
            "O tema só é aplicado depois de reiniciar o programa.\n\n"
            "Reiniciar agora?", sim="Reiniciar agora", nao="Depois")

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

    def _ola(self, texto):
        nome = _primeiro_nome(texto)
        if nome:
            self._titulo.setText(f"Olá, {nome}")
            self._subtitulo.setText("Que bom te ver. Digite a senha para continuar.")
        else:
            self._titulo.setText("Entrar no Vertex")
            self._subtitulo.setText("Use o e-mail e a senha cadastrados na loja.")

    def eventFilter(self, observado, evento):
        # aviso de Caps Lock ao digitar a senha
        if (
            observado is getattr(self, "senha", None)
            and evento.type() == QEvent.KeyPress
            and evento.text()
            and evento.text().isalpha()
        ):
            caps = evento.text().isupper() and not (evento.modifiers() & Qt.ShiftModifier)
            if caps:
                self._aviso.setStyleSheet(self._estilo_aviso(tokens.ALERTA_TEXTO))
                self._aviso.setText("Caps Lock está ligado")
            elif self._aviso.text().startswith("Caps"):
                self._limpar_aviso(tudo=True)
        return super().eventFilter(observado, evento)

    def _limpar_aviso(self, tudo=False):
        # o aviso de Caps Lock so sai quando a pessoa desliga a tecla
        if self._aviso.text() and (tudo or not self._aviso.text().startswith("Caps")):
            self._aviso.setText("")

    def _mostrar_erro(self, texto):
        self._aviso.setStyleSheet(self._estilo_aviso(tokens.ERRO))
        self._aviso.setText(texto)
        self._tremor_i = 0
        self._tremor_timer.start()

    def _andar_tremor(self):
        self._tremor_i += 1
        dx = int(math.sin(self._tremor_i * 0.9) * 12 * max(0.0, 1 - self._tremor_i / 26))
        self._lay.setContentsMargins(self.MARGEM + dx, 0, self.MARGEM - dx, 0)
        if self._tremor_i > 26:
            self._tremor_timer.stop()
            self._lay.setContentsMargins(self.MARGEM, 0, self.MARGEM, 0)

    # ======================================
    # COMPORTAMENTO
    # ======================================

    def ir_para_cadastro(self):

        from telas.cadastro_inicial import CadastroInicialWindow

        self.cadastro = CadastroInicialWindow()
        self.cadastro.show()
        self.close()

    def alternar_ver_senha(self):

        mostrar = self.senha.echoMode() == QLineEdit.Password
        self.senha.setEchoMode(QLineEdit.Normal if mostrar else QLineEdit.Password)
        self._acao_ver.setIcon(icone("eye-off" if mostrar else "eye", tokens.TEXTO_TERCIARIO, 19))

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
            self._mostrar_erro("Informe o e-mail.")
            self.usuario.setFocus()
            return

        if not self.senha.text():
            self._mostrar_erro("Digite a senha para entrar.")
            self.senha.setFocus()
            return

        if not self.botao.isEnabled():
            # ja tem um login em andamento -- clique duplo (ou Enter
            # depois de clicar) so' faria bater no backend duas vezes.
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
        # depois de um login ok o botao fica no "Bem-vindo!" ate a tela abrir
        if getattr(self.botao, "estado", "idle") != "ok":
            self._definir_entrando(False)

    def _definir_entrando(self, entrando: bool):

        if hasattr(self.botao, "definir"):
            self.botao.definir("carregando" if entrando else "idle")
        else:
            self.botao.setEnabled(not entrando)
        self.usuario.setEnabled(not entrando)
        self.senha.setEnabled(not entrando)

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

            self._mostrar_erro(erro or "E-mail ou senha incorretos. Confira e tente de novo.")

    def _abrir_principal(self):

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        if hasattr(self.botao, "definir"):
            self.botao.texto_ok = "Bem-vindo!"
            self.botao.definir("ok")

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
        self._definir_entrando(False)
        QMessageBox.critical(
            self,
            "Erro",
            f"Login feito, mas não foi possível abrir o sistema.\n{erro}",
        )

    def _ao_buscar_info_principal_sucesso(self, resultado):

        info_usuario, config = resultado

        self.principal = PrincipalWindow(info_usuario, config)

        if not self.isVisible() or movimento_reduzido():
            self._mostrar_principal()
            return

        # revelacao: um circulo cresce do botao e cobre a tela; quando
        # cobriu, troca pra janela principal
        nome = ""
        if isinstance(info_usuario, dict):
            nome = (info_usuario.get("nome") or "").split(" ")[0]
        self._onda.nome = nome or _primeiro_nome(self.usuario.text()) or "!"
        centro = self.botao.mapTo(self, self.botao.rect().center())
        self._onda.centro = QPointF(centro)
        self._onda.p = 0.0
        self._onda.show()
        self._onda.raise_()
        self._onda_timer.start()

    def _andar_onda(self):
        self._onda.p += 0.016 / 1.1
        self._onda.update()
        if self._onda.p > 1.15:
            self._onda_timer.stop()
            self._mostrar_principal()

    def _mostrar_principal(self):
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
