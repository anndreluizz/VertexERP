import base64
import math

from PySide6.QtCore import QPoint, QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from requests.exceptions import ConnectionError

from design import tokens
from design.fonts import familia_titulo
from design.icons import icone
from design.login_visual import (
    D,
    PASSOS_NOMES,
    BotaoEntrar,
    Confete,
    FundoBV,
    Onda,
    forca,
)
from services.api import atualizar_configuracoes, cadastrar_usuario, configuracoes, login, me
from services.worker import em_paralelo, rodar_em_thread
from utils.acessibilidade import movimento_reduzido
from utils.validacao import email_valido

T = tokens
LIMITE_LOGO = 2 * 1024 * 1024


def _criar_conta_e_logar(nome, email, senha):
    """Roda na worker thread -- cadastro do primeiro/novo usuario
    seguido de login automatico com a mesma credencial."""

    response = cadastrar_usuario(nome, email, senha)

    if response.status_code != 200:
        return response, None

    eh_primeiro_usuario = response.json().get("data", {}).get("admin", False)
    ok, erro_login, _verificacao_id = login(email, senha)

    return response, (eh_primeiro_usuario, ok, erro_login)


def _buscar_info_principal():
    """Roda na worker thread -- mesmo raciocinio de
    telas/login.py::_buscar_info_principal (duplicado aqui de proposito
    em vez de importar de lá, pra nao criar acoplamento entre as duas
    telas de entrada por causa de uma funcao de 1 linha). As duas sao
    independentes, entao disparam em paralelo."""
    return em_paralelo((me,), (configuracoes,))


def _erro_email(texto):
    return None if email_valido(texto) and "@" in texto else "Esse e-mail parece incompleto (ex.: voce@loja.com)."


def _erro_senha(texto):
    return None if len(texto) >= 6 else "A senha precisa ter pelo menos 6 caracteres."


def _erro_confirmacao(texto):
    return None if texto == D.get("senha") else "A confirmação não é igual à senha."


def _dados_finais(incluir_pix):
    """Payload de configuracoes das etapas Contato e Recebimento (so o que foi preenchido)."""
    dados = {}
    if D.get("tel"):
        dados["telefone"] = D["tel"].strip()
    if D.get("end"):
        dados["endereco"] = D["end"].strip()
    if incluir_pix and D.get("pix"):
        dados["pix_chave"] = D["pix"].strip()
        # o QR do Pix limita o nome a 25 caracteres; cidade fica pra Configuracoes
        dados["pix_nome"] = (D.get("loja") or "")[:25]
    if incluir_pix and D.get("logo_bytes"):
        dados["logo_base64"] = base64.b64encode(D["logo_bytes"]).decode("ascii")
    return dados


class _CartaoAcao(QFrame):
    """Atalho da tela final: clicar escolhe a tela que abre ao entrar."""

    clicado = Signal()

    def mousePressEvent(self, e):
        self.clicado.emit()
        super().mousePressEvent(e)


class CadastroInicialWindow(QWidget):
    """Primeiro acesso: criar a conta (admin) e montar a loja, em 5 etapas
    com a previa da loja ao vivo na esquerda. Visual em design/login_visual.py."""

    MARGEM = 64

    PASSOS = [
        dict(titulo="Vamos começar por você", sub="Você será o administrador da loja.",
             campos=[("Seu nome completo", "nome", "Ex.: André Lopes", "user", True, None),
                     ("Seu e-mail (é o seu login)", "email", "voce@loja.com", "mail", True, _erro_email)]),
        dict(titulo="Crie uma senha de acesso", sub="Mínimo de 6 caracteres. Você troca quando quiser.",
             botao="Criar minha conta", carrega="Criando…", termos=True, voltar=True,
             campos=[("Senha", "senha", "Crie uma senha", "lock", True, _erro_senha),
                     ("Confirmar senha", "conf", "Digite de novo", "lock", True, _erro_confirmacao)]),
        dict(titulo="Como se chama a sua loja?", sub="O nome aparece no PDV, nos recibos e nos comprovantes.",
             campos=[("Nome da loja", "loja", "Ex.: Papelaria da Ana", "store", True, None),
                     ("CNPJ ou CPF", "cnpj", "00.000.000/0001-00", "file-text", False, None)]),
        dict(titulo="Como os clientes falam com você?", sub="Aparece no recibo e na cobrança de fiado pelo WhatsApp.",
             opcional=True,
             campos=[("WhatsApp / telefone", "tel", "(00) 00000-0000", "message-circle", False, None),
                     ("Endereço", "end", "Rua, número, cidade", "home", False, None)]),
        dict(titulo="Quer receber por Pix?",
             sub="Opcional. A chave vira o QR Code do cupom. A logo você pode enviar agora ou depois.",
             opcional=True, botao="Concluir", carrega="Montando sua loja…", logo=True,
             campos=[("Chave Pix", "pix", "CPF, CNPJ, e-mail ou celular", "dollar-sign", False, None)]),
    ]

    def __init__(self):
        super().__init__()
        D.clear()

        self.setWindowTitle("Vertex ERP - Primeiro Acesso")
        self.resize(1180, 760)
        self.setMinimumSize(1000, 680)
        self.setWindowState(Qt.WindowMaximized)
        self.setStyleSheet(f"background:{T.CARD};")

        raiz = QHBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)
        self._fundo = FundoBV()
        raiz.addWidget(self._fundo, 56)
        self._painel = QWidget()
        self._painel.setMinimumWidth(520)
        raiz.addWidget(self._painel, 44)
        self._lay = QVBoxLayout(self._painel)
        self._lay.setContentsMargins(self.MARGEM, 0, self.MARGEM, 0)
        self._lay.setSpacing(0)

        self._confete = Confete(self)
        self._onda = Onda(self)
        self._onda.setGeometry(self.rect())
        self._onda_timer = QTimer(self)
        self._onda_timer.setInterval(16)
        self._onda_timer.timeout.connect(self._andar_onda)
        self._tremor_timer = QTimer(self)
        self._tremor_timer.setInterval(16)
        self._tremor_timer.timeout.connect(self._andar_tremor)
        self._tremor_i = 0

        self.n = 0
        self.campos = []
        self.eh_primeiro_usuario = True
        self.ir(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        onda = getattr(self, "_onda", None)
        if onda is not None:
            onda.setGeometry(self.rect())

    def closeEvent(self, event):
        fundo = getattr(self, "_fundo", None)
        if fundo is not None:
            fundo.parar_animacao()
        super().closeEvent(event)

    # ======================================
    # MONTAGEM DE CADA ETAPA
    # ======================================

    def _limpar(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                self._limpar(item.layout())

    def _linha_progresso(self, n):
        h = QHBoxLayout()
        h.setContentsMargins(0, 26, 0, 0)
        h.setSpacing(6)
        # "Voltar" so' ate a conta ser criada (depois ela ja existe)
        if n == 1:
            v = QPushButton("Voltar")
            v.setIcon(icone("chevron-left", T.TEXTO_SECUNDARIO, 16))
            v.setCursor(Qt.PointingHandCursor)
            v.setAutoDefault(False)
            v.setStyleSheet(
                f"QPushButton{{border:none;background:transparent;color:{T.TEXTO_SECUNDARIO};"
                f"font-size:{T.TAMANHO_BASE}px;font-weight:600;}}QPushButton:hover{{color:{T.TEXTO};}}"
            )
            v.clicked.connect(lambda: self.ir(0))
            h.addWidget(v)
        h.addStretch()
        for i in range(5):
            s = QFrame()
            s.setFixedSize(34, 6)
            s.setStyleSheet(f"background:{T.PRIMARIA if i <= n else T.BORDA};border-radius:3px;")
            h.addWidget(s)
        return h

    def _rotulo(self, texto, obrigatorio):
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        a = QLabel(texto)
        a.setStyleSheet(
            f"background:transparent;color:{T.TEXTO_SECUNDARIO};font-size:{T.TAMANHO_SM}px;font-weight:700;"
        )
        b = QLabel("obrigatório" if obrigatorio else "opcional")
        b.setStyleSheet(f"background:transparent;color:{T.TEXTO_TERCIARIO};font-size:{T.TAMANHO_XS}px;")
        h.addWidget(a)
        h.addWidget(b)
        h.addStretch()
        return w

    def _campo(self, placeholder, nome_icone, senha):
        c = QLineEdit()
        c.setPlaceholderText(placeholder)
        c.setFixedHeight(52)
        c.addAction(icone(nome_icone, T.TEXTO_TERCIARIO, 19), QLineEdit.LeadingPosition)
        if senha:
            c.setEchoMode(QLineEdit.Password)
        c.setStyleSheet(
            f"QLineEdit{{border:1.5px solid {T.BORDA_CAMPO};border-radius:{T.RADIUS_MD}px;padding:0 14px;"
            f"background:{T.CARD};color:{T.TEXTO};font-size:{T.TAMANHO_MD}px;}}"
            f"QLineEdit:focus{{border:2px solid {T.PRIMARIA};}}"
        )
        return c

    def _botao_texto(self, texto, cor=None):
        b = QPushButton(texto)
        b.setCursor(Qt.PointingHandCursor)
        b.setAutoDefault(False)
        cor = cor or T.TEXTO_SECUNDARIO
        b.setStyleSheet(
            f"QPushButton{{border:none;background:transparent;color:{cor};font-size:{T.TAMANHO_BASE}px;"
            f"font-weight:600;padding:12px;}}QPushButton:hover{{color:{T.TEXTO};}}"
        )
        return b

    def ir(self, n):
        self.n = n
        self._limpar(self._lay)
        self._fundo.passos.atual = n
        if n >= 5:
            self._pronto()
            return
        p = self.PASSOS[n]
        lay = self._lay
        lay.addLayout(self._linha_progresso(n))
        lay.addStretch(2)
        etapa = QLabel(f"ETAPA {n + 1} DE 5  ·  {PASSOS_NOMES[n].upper()}")
        etapa.setStyleSheet(
            f"background:transparent;color:{T.PRIMARIA};font-size:{T.TAMANHO_XS}px;"
            f"font-weight:800;letter-spacing:1.4px;"
        )
        lay.addWidget(etapa)
        lay.addSpacing(8)
        t = QLabel(p["titulo"])
        t.setWordWrap(True)
        t.setStyleSheet(
            f"background:transparent;color:{T.TEXTO};font-size:32px;font-weight:800;"
            f"font-family:'{familia_titulo()}';"
        )
        lay.addWidget(t)
        lay.addSpacing(6)
        s = QLabel(p["sub"])
        s.setWordWrap(True)
        s.setStyleSheet(f"background:transparent;color:{T.TEXTO_SECUNDARIO};font-size:{T.TAMANHO_MD}px;")
        lay.addWidget(s)
        lay.addSpacing(26)

        self.campos = []
        for rotulo, chave, ph, nome_icone, obrig, valida in p["campos"]:
            lay.addWidget(self._rotulo(rotulo, obrig))
            lay.addSpacing(8)
            c = self._campo(ph, nome_icone, chave in ("senha", "conf"))
            c.setText(D.get(chave, ""))
            erro = QLabel("")
            erro.setStyleSheet(
                f"background:transparent;color:{T.ERRO};font-size:{T.TAMANHO_SM}px;font-weight:600;"
            )
            erro.setFixedHeight(24)
            erro.setContentsMargins(0, 5, 0, 0)
            c.textChanged.connect(
                lambda tx, ch=chave, er=erro: (
                    D.__setitem__(ch, tx), er.setText(""), self._forca() if ch == "senha" else None
                )
            )
            lay.addWidget(c)
            lay.addWidget(erro)
            self.campos.append((chave, c, erro, obrig, valida))
            if chave == "senha":
                medidor = QHBoxLayout()
                medidor.setSpacing(5)
                self._barras = []
                for _ in range(4):
                    b = QFrame()
                    b.setFixedHeight(5)
                    self._barras.append(b)
                    medidor.addWidget(b, 1)
                self._lbl_forca = QLabel("")
                self._lbl_forca.setStyleSheet(
                    f"background:transparent;color:{T.TEXTO_TERCIARIO};font-size:{T.TAMANHO_XS}px;font-weight:700;"
                )
                lay.addLayout(medidor)
                lay.addWidget(self._lbl_forca)
                lay.addSpacing(6)
                self._forca()
            else:
                lay.addSpacing(8)

        if p.get("termos"):
            self.termos = QCheckBox("Aceito os Termos de uso e a Política de Privacidade")
            self.termos.setStyleSheet(
                f"background:transparent;color:{T.TEXTO_SECUNDARIO};font-size:{T.TAMANHO_SM}px;"
            )
            self.termos.setCursor(Qt.PointingHandCursor)
            lay.addWidget(self.termos)
            lay.addSpacing(6)
        if p.get("logo"):
            b = QPushButton("  Escolher a logo da loja")
            b.setIcon(icone("plus", T.PRIMARIA, 18))
            b.setCursor(Qt.PointingHandCursor)
            b.setAutoDefault(False)
            b.setFixedHeight(48)
            b.setStyleSheet(
                f"QPushButton{{border:1.5px dashed {T.BORDA_FORTE};border-radius:{T.RADIUS_MD}px;"
                f"background:{T.CARD};color:{T.PRIMARIA};font-size:{T.TAMANHO_BASE}px;font-weight:700;}}"
                f"QPushButton:hover{{background:{T.PRIMARIA_CLARA};border-color:{T.PRIMARIA};}}"
            )
            b.clicked.connect(self._escolher_logo)
            lay.addWidget(b)
            lay.addSpacing(4)
        lay.addSpacing(10)

        self.botao = BotaoEntrar()
        self.botao.rotulo = p.get("botao", "Continuar")
        self.botao.rotulo_carregando = p.get("carrega", "Continuar")
        self.botao.clicked.connect(self.avancar)
        lay.addWidget(self.botao)

        if p.get("opcional"):
            pular = self._botao_texto("Pular por enquanto")
            pular.clicked.connect(self._pular)
            lay.addWidget(pular)
        if n == 0:
            lay.addSpacing(14)
            linha = QHBoxLayout()
            linha.setSpacing(6)
            linha.addStretch()
            lbl = QLabel("Já tem uma conta?")
            lbl.setStyleSheet(
                f"background:transparent;color:{T.TEXTO_SECUNDARIO};font-size:{T.TAMANHO_BASE}px;"
            )
            acessar = self._botao_texto("Acessar minha conta", T.PRIMARIA)
            acessar.setStyleSheet(acessar.styleSheet().replace("padding:12px", "padding:2px 0").replace(
                "font-weight:600", "font-weight:700"))
            acessar.clicked.connect(self.ir_para_login)
            linha.addWidget(lbl)
            linha.addWidget(acessar)
            linha.addStretch()
            lay.addLayout(linha)
        lay.addStretch(3)

        for i, (_, c, *_r) in enumerate(self.campos):
            c.returnPressed.connect(lambda i=i: self._enter(i))
        self.campos[0][1].setFocus()

    def _forca(self):
        n, texto = forca(D.get("senha", ""))
        cores = [T.ERRO, T.ERRO, T.ALERTA, T.SECUNDARIA, T.SUCESSO]
        for i, b in enumerate(self._barras):
            b.setStyleSheet(f"background:{cores[n] if i < n else T.BORDA};border-radius:2px;")
        self._lbl_forca.setText(texto)

    def _escolher_logo(self):
        arquivo, _ = QFileDialog.getOpenFileName(
            self, "Escolha a logo", "", "Imagens (*.png *.jpg *.jpeg *.webp)"
        )
        if not arquivo:
            return
        try:
            with open(arquivo, "rb") as f:
                dados = f.read()
        except OSError as e:
            QMessageBox.warning(self, "Logo", f"Não consegui abrir a imagem.\n{e}")
            return
        pix = QPixmap()
        if len(dados) > LIMITE_LOGO or not pix.loadFromData(dados):
            QMessageBox.warning(self, "Logo", "Escolha uma imagem PNG, JPG ou WEBP de até 2 MB.")
            return
        D["logo_bytes"] = dados
        D["logo"] = pix

    def _enter(self, i):
        if i + 1 < len(self.campos):
            self.campos[i + 1][1].setFocus()
        else:
            self.avancar()

    # ======================================
    # FLUXO
    # ======================================

    def avancar(self):
        if self.botao.estado != "idle":
            return

        ok = True
        for chave, c, erro, obrig, valida in self.campos:
            texto = c.text().strip()
            msg = None
            if obrig and not texto:
                msg = "Preencha este campo para continuar."
            elif valida and (texto or obrig):
                msg = valida(c.text())
            if msg:
                erro.setText(msg)
                ok = False
        if ok and self.PASSOS[self.n].get("termos") and not self.termos.isChecked():
            self.campos[-1][2].setText("Aceite os termos para criar a conta.")
            ok = False
        if not ok:
            self._tremer()
            return

        if self.n == 1:
            self._criar_conta()
        elif self.n == 2:
            self._salvar_loja_e_seguir()
        elif self.n == 4:
            self._concluir(incluir_pix=True)
        else:
            self.ir(self.n + 1)

    def _pular(self):
        if self.n == 4:
            self._concluir(incluir_pix=False)
        else:
            self.ir(self.n + 1)

    # ---- etapa 2: cria a conta e ja entra com ela
    def _criar_conta(self):
        self.botao.definir("carregando")
        rodar_em_thread(
            self,
            _criar_conta_e_logar,
            D.get("nome", "").strip(),
            D.get("email", "").strip(),
            D.get("senha", ""),
            ao_sucesso=self._ao_criar_conta_sucesso,
            ao_erro=self._ao_criar_conta_erro,
        )

    def _ao_criar_conta_sucesso(self, resultado):
        response, pos_login = resultado

        if response.status_code != 200:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            self.botao.definir("idle")
            self.campos[0][2].setText(str(erro))
            self._tremer()
            return

        eh_primeiro_usuario, ok, _erro_login = pos_login

        if not ok:
            self.botao.definir("idle")
            QMessageBox.critical(
                self,
                "Erro",
                "Conta criada, mas não foi possível entrar automaticamente. Tente acessar manualmente.",
            )
            return

        self.eh_primeiro_usuario = eh_primeiro_usuario
        self.botao.texto_ok = "Conta criada!"
        self.botao.definir("ok")
        # so' o primeiro usuario (admin) monta a loja; os outros vao direto pro fim
        QTimer.singleShot(700, lambda: self.ir(2 if eh_primeiro_usuario else 5))

    def _ao_criar_conta_erro(self, erro):
        self.botao.definir("idle")
        if isinstance(erro, ConnectionError):
            QMessageBox.critical(
                self,
                "Servidor Offline",
                "Não foi possível conectar ao Backend.\n\nVerifique se o FastAPI está executando.",
            )
            return
        QMessageBox.critical(self, "Erro", str(erro))

    # ---- etapa 3: nome da loja (o nome ja fica salvo aqui, mesmo se fechar a tela depois)
    def _salvar_loja_e_seguir(self):
        dados = {"nome_loja": D.get("loja", "").strip()}
        if D.get("cnpj"):
            dados["cnpj_cpf"] = D["cnpj"].strip()
        self._salvar(dados)
        self.ir(3)

    def _salvar(self, dados, ao_fim=None):
        # rodar_em_thread so' aceita metodos de QObject como callback, entao
        # o "o que fazer depois" fica guardado na janela
        self._ao_fim_salvar = ao_fim
        rodar_em_thread(
            self,
            atualizar_configuracoes,
            dados,
            ao_sucesso=self._ao_salvar,
            ao_erro=self._ao_salvar_erro,
        )

    def _depois_de_salvar(self):
        ao_fim, self._ao_fim_salvar = getattr(self, "_ao_fim_salvar", None), None
        if ao_fim:
            ao_fim()

    def _ao_salvar(self, response):
        if response.status_code != 200:
            self._aviso_salvar()
        self._depois_de_salvar()

    def _ao_salvar_erro(self, _erro):
        self._aviso_salvar()
        self._depois_de_salvar()

    def _aviso_salvar(self):
        QMessageBox.warning(
            self,
            "Dados da loja",
            "Não consegui salvar alguns dados da loja agora. "
            "Você pode completar depois em Configurações.",
        )

    # ---- etapa 5: salva contato + Pix/logo e mostra a tela final
    def _concluir(self, incluir_pix):
        dados = _dados_finais(incluir_pix)

        def fim():
            self.botao.texto_ok = "Pronto!"
            self.botao.definir("ok")
            QTimer.singleShot(700, lambda: self.ir(5))

        self.botao.definir("carregando")
        if dados:
            self._salvar(dados, ao_fim=fim)
        else:
            QTimer.singleShot(600, fim)

    # ---- tela final
    def _pronto(self):
        nome = (D.get("nome") or "").split()[0] if D.get("nome") else ""
        lay = self._lay
        self._fundo.frase1, self._fundo.frase2 = "Tudo pronto.", "Bora vender?"
        self._fundo.sub = "Sua loja está configurada e esperando o primeiro cliente."
        lay.addLayout(self._linha_progresso(5))
        lay.addStretch(2)
        ic = QLabel()
        ic.setFixedSize(76, 76)
        ic.setAlignment(Qt.AlignCenter)
        ic.setPixmap(icone("check", "#FFFFFF", 38).pixmap(38, 38))
        ic.setStyleSheet(f"background:{T.SUCESSO};border-radius:38px;")
        lay.addWidget(ic)
        lay.addSpacing(18)
        t = QLabel(f"Tudo pronto, {nome}!" if nome else "Tudo pronto!")
        t.setStyleSheet(
            f"background:transparent;color:{T.TEXTO};font-size:34px;font-weight:800;"
            f"font-family:'{familia_titulo()}';"
        )
        lay.addWidget(t)
        lay.addSpacing(6)
        loja = D.get("loja")
        s = QLabel(
            f"A {loja} já está no Vertex. Que tal começar por aqui?" if loja
            else "Sua conta está pronta. Que tal começar por aqui?"
        )
        s.setWordWrap(True)
        s.setStyleSheet(f"background:transparent;color:{T.TEXTO_SECUNDARIO};font-size:{T.TAMANHO_MD}px;")
        lay.addWidget(s)
        lay.addSpacing(22)

        self._cartoes = []
        D["destino"] = None
        for chave, nome_icone, titulo, sub in (
            ("produtos", "package", "Cadastrar o primeiro produto", "Bipe o código ou digite o nome"),
            ("clientes", "users", "Cadastrar um cliente", "Para vender no fiado depois"),
            ("caixa", "wallet", "Abrir o caixa", "Informe o troco inicial e comece a vender"),
        ):
            c = _CartaoAcao()
            c.setObjectName("pc")
            c.setCursor(Qt.PointingHandCursor)
            c.setFixedHeight(64)
            h = QHBoxLayout(c)
            h.setContentsMargins(14, 0, 14, 0)
            h.setSpacing(12)
            i = QLabel()
            i.setFixedSize(38, 38)
            i.setAlignment(Qt.AlignCenter)
            i.setPixmap(icone(nome_icone, T.PRIMARIA, 19).pixmap(19, 19))
            i.setStyleSheet(f"background:{T.PRIMARIA_CLARA};border-radius:{T.RADIUS_SM + 1}px;border:none;")
            h.addWidget(i)
            col = QVBoxLayout()
            col.setSpacing(0)
            a = QLabel(titulo)
            a.setStyleSheet(
                f"background:transparent;border:none;color:{T.TEXTO};font-size:{T.TAMANHO_BASE}px;font-weight:700;"
            )
            b = QLabel(sub)
            b.setStyleSheet(
                f"background:transparent;border:none;color:{T.TEXTO_TERCIARIO};font-size:{T.TAMANHO_XS}px;"
            )
            col.addStretch()
            col.addWidget(a)
            col.addWidget(b)
            col.addStretch()
            h.addLayout(col, 1)
            seta = QLabel()
            seta.setPixmap(icone("chevron-right", T.TEXTO_TERCIARIO, 18).pixmap(18, 18))
            seta.setStyleSheet("background:transparent;border:none;")
            h.addWidget(seta)
            c.clicado.connect(lambda ch=chave: self._escolher_destino(ch))
            self._cartoes.append((chave, c))
            lay.addWidget(c)
            lay.addSpacing(10)
        self._escolher_destino(None)
        lay.addSpacing(8)

        self.botao = BotaoEntrar()
        self.botao.rotulo = "Entrar na minha loja"
        self.botao.rotulo_carregando = "Abrindo…"
        self.botao.clicked.connect(self._entrar)
        lay.addWidget(self.botao)
        lay.addStretch(3)
        QTimer.singleShot(350, self._festa)

    def _escolher_destino(self, chave):
        """Destaca o atalho escolhido (clicar de novo desmarca)."""
        D["destino"] = None if D.get("destino") == chave else chave
        for ch, c in self._cartoes:
            ativo = D["destino"] == ch
            c.setStyleSheet(
                f"QFrame#pc{{background:{T.PRIMARIA_CLARA if ativo else T.CARD};"
                f"border:{2 if ativo else 1}px solid {T.PRIMARIA if ativo else T.BORDA};"
                f"border-radius:{T.RADIUS_MD}px;}}"
                f"QFrame#pc:hover{{border-color:{T.PRIMARIA};background:{T.PRIMARIA_CLARA};}}"
            )

    def _festa(self):
        if movimento_reduzido() or not self.isVisible():
            return
        c = self._painel.mapTo(self, QPoint(self._painel.width() // 2, 140))
        self._confete.disparar(c.x(), c.y() + 40)

    # ---- abre o sistema
    def _entrar(self):
        if self.botao.estado != "idle":
            return
        self.botao.definir("carregando")
        rodar_em_thread(
            self,
            _buscar_info_principal,
            ao_sucesso=self._ao_buscar_info_principal_sucesso,
            ao_erro=self._ao_buscar_info_principal_erro,
        )

    def _ao_buscar_info_principal_erro(self, erro):
        self.botao.definir("idle")
        QMessageBox.critical(
            self,
            "Erro",
            f"Conta criada, mas não foi possível abrir o sistema.\n{erro}",
        )

    def _ao_buscar_info_principal_sucesso(self, resultado):
        from telas.principal import PrincipalWindow

        info_usuario, config = resultado
        self.principal = PrincipalWindow(info_usuario, config)

        if not self.isVisible() or movimento_reduzido():
            self._mostrar_principal()
            return

        self._onda.nome = (D.get("nome") or "").split(" ")[0] or "!"
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
        destino = D.get("destino")
        if destino:
            try:
                self.principal._exibir_pagina(destino, getattr(self.principal, destino))
            except Exception:
                pass  # o atalho e' so' um empurrao: se falhar, fica no Inicio
        self.close()

    # ---- tremor de erro (igual ao do login)
    def _tremer(self):
        self._tremor_i = 0
        self._tremor_timer.start()

    def _andar_tremor(self):
        self._tremor_i += 1
        dx = int(math.sin(self._tremor_i * 0.9) * 12 * max(0.0, 1 - self._tremor_i / 26))
        self._lay.setContentsMargins(self.MARGEM + dx, 0, self.MARGEM - dx, 0)
        if self._tremor_i > 26:
            self._tremor_timer.stop()
            self._lay.setContentsMargins(self.MARGEM, 0, self.MARGEM, 0)

    def ir_para_login(self):

        from telas.login import LoginWindow

        self.login = LoginWindow()
        self.login.show()
        self.close()
