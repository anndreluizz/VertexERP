from datetime import datetime

from telas.suprimento import SuprimentoWindow
from telas.sangria import SangriaWindow
from telas.abrir_caixa import AbrirCaixaWindow
from telas.fechar_caixa import FecharCaixaWindow

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QDialog,
    QMessageBox,
    QStackedWidget,
    QScrollArea,
    QLineEdit,
    QProgressBar,
)

from services.caixa_service import (
    caixa_aberto,
    abrir_caixa,
    resumo_caixa,
    listar_movimentos_caixa,
)

from services.movimento_caixa_service import (
    criar_sangria,
    criar_suprimento,
)

from design import tokens
from design.icons import icone_pixmap
from design.privacidade import botao_olho, privacidade
from design.widgets import Badge, BotaoPerigo, BotaoSecundario, BotaoSucesso, cor_forma_pagamento
from services.worker import rodar_em_thread, em_paralelo
from services import api
from telas.relatorios import NOMES_FORMA_PAGAMENTO
from telas.inicio import _Numero, _cartao, _rotulo
from utils.formatacao import formatar_moeda, ler_moeda


_INFO_TIPO_MOVIMENTO = {
    "VENDA": ("Venda", "info"),
    "SUPRIMENTO": ("Suprimento", "sucesso"),
    "SANGRIA": ("Sangria", "erro"),
    "RECEBIMENTO_FIADO": ("Recebimento fiado", "sucesso"),
    "ESTORNO": ("Estorno", "alerta"),
    # venda/estorno no fiado (forma PRAZO) nao mexem no dinheiro do caixa
    "VENDA_FIADO": ("Venda fiado", "neutro"),
    "ESTORNO_FIADO": ("Fiado cancelado", "neutro"),
    "PAGAMENTO": ("Conta paga", "erro"),
}


def _texto_abertura(texto):
    """"Aberto hoje às 17:27" / "Aberto ontem às 22:10" / "Aberto em
    03/10 às 08:00" -- antes aparecia a data crua "2026-10-05 17:27"."""

    try:
        dt = datetime.fromisoformat(str(texto).replace("T", " ")[:19])
    except ValueError:
        return f"Aberto em {str(texto or '')[:16]}"

    hoje = datetime.now().date()
    hora = dt.strftime("%H:%M")
    if dt.date() == hoje:
        return f"Aberto hoje às {hora}"
    if (hoje - dt.date()).days == 1:
        return f"Aberto ontem às {hora}"
    return f"Aberto em {dt.strftime('%d/%m')} às {hora}"


def _tempo_aberto(texto, agora=None):
    """"há 2h45" / "há 35 min" desde a abertura -- ajuda a ver de longe o
    caixa chegando nas 24h (depois disso ele bloqueia as vendas)."""
    try:
        dt = datetime.fromisoformat(str(texto).replace("T", " ")[:19])
    except ValueError:
        return ""
    minutos = max(0, int(((agora or datetime.now()) - dt).total_seconds() // 60))
    if minutos < 60:
        return f"há {minutos} min"
    return f"há {minutos // 60}h{minutos % 60:02d}"


def fatias_formas(resumo):
    """[(rotulo, forma, valor)] do que ENTROU no turno, por forma (vendas
    + fiado recebido), so' as que tiveram valor -- pra barra colorida."""
    v = lambda chave: float((resumo or {}).get(chave, 0) or 0)
    fatias = [
        ("Dinheiro", "DINHEIRO", v("vendas_dinheiro") + v("recebimentos_fiado_dinheiro")),
        ("Pix", "PIX", v("vendas_pix") + v("recebimentos_fiado_pix")),
        ("Cartão", "CARTAO", v("vendas_cartao") + v("recebimentos_fiado_cartao")),
        ("Outras", "CHEQUE", v("recebimentos_fiado_outros")),
    ]
    return [f for f in fatias if f[2] >= 0.01]


_TIPOS_SO_FIADO = ("VENDA_FIADO", "ESTORNO_FIADO")


def _tipo_exibido(mov):
    tipo = mov.get("tipo", "")
    if mov.get("forma_pagamento") == "PRAZO" and tipo in ("VENDA", "ESTORNO"):
        return tipo + "_FIADO"
    return tipo


def _descricao_movimento(mov, tipo_exibido):
    descricao = mov.get("descricao") or ""
    # "Estorno da venda #146" -> "Venda #146 cancelada": liga o estorno a' venda
    if descricao.startswith("Estorno da venda "):
        descricao = f"Venda {descricao[len('Estorno da venda '):]} cancelada"
    if tipo_exibido in _TIPOS_SO_FIADO:
        descricao += " · não mexe no dinheiro do caixa"
    return descricao


def _cor_valor_movimento(tipo):
    if tipo in ("SUPRIMENTO", "VENDA", "RECEBIMENTO_FIADO"):
        return tokens.SECUNDARIA_HOVER
    if tipo in ("SANGRIA", "ESTORNO"):
        return tokens.ERRO
    if tipo in _TIPOS_SO_FIADO:
        return tokens.TEXTO_SECUNDARIO
    return tokens.TEXTO


def _celula_valor_movimento(tipo, texto_valor):
    """QLabel colorido pro valor do movimento -- precisa ser um cell
    widget (não um QTableWidgetItem comum) porque o QSS da tabela
    ("QTableWidget::item { color: ... }") tem prioridade sobre
    setForeground(), então colorir o item direto não teria efeito."""

    container = QWidget()
    container.setStyleSheet("background:transparent;")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(12, 0, 12, 0)
    layout.setSpacing(0)

    lbl = QLabel()
    privacidade.definir_texto(lbl, texto_valor)
    lbl.setStyleSheet(f"""
        background:transparent; color:{_cor_valor_movimento(tipo)};
        font-weight:700; font-size:{tokens.TAMANHO_BASE}px;
    """)
    layout.addWidget(lbl)
    layout.addStretch()

    return container


def _pill_tipo_movimento(tipo):
    """Etiqueta colorida (pill) pra cada tipo de movimento no histórico
    do caixa -- mesma linguagem visual das pills de tipo usadas na
    timeline da ficha do cliente."""

    rotulo, variante = _INFO_TIPO_MOVIMENTO.get(
        tipo, (tipo.replace("_", " ").title() if tipo else "—", "neutro")
    )

    fundo, cor_texto = Badge.variantes()[variante]

    container = QWidget()
    container.setStyleSheet("background:transparent;")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(10, 0, 0, 0)
    layout.setSpacing(0)

    pill = QLabel(rotulo)
    pill.setStyleSheet(f"""
        background:{fundo}; color:{cor_texto};
        border-radius:{tokens.RADIUS_PILL}px;
        font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        padding:3px 10px;
    """)
    # centralizada na vertical -- sem o alinhamento a etiqueta
    # esticava até a altura inteira da linha
    layout.addWidget(pill, 0, Qt.AlignVCenter)
    layout.addStretch()

    return container


def formas_entrada(resumo):
    """[(rotulo, forma, valor, pct)] pras barras 'Entrou por forma': o que
    entrou por forma + o fiado lancado (fora da gaveta). pct e' sobre o
    que entrou de verdade (sem o fiado), como no prototipo."""
    fatias = fatias_formas(resumo)
    total = sum(f[2] for f in fatias)
    prazo = float((resumo or {}).get("vendas_prazo", 0) or 0)
    if prazo >= 0.01:
        fatias.append(("Fiado (fora da gaveta)", "PRAZO", prazo))
    return [(r, f, v, min(100, round(100 * v / total)) if total else 100) for r, f, v in fatias]


def _plural(n, um, varios):
    return f"{n} {um if n == 1 else varios}"


def numeros_caixa(resumo, movimentos):
    """Os 4 cartoes do topo do caixa: abertura, entrou, saiu e esperado
    na gaveta, com a nota de quantas vendas/sangrias foram."""
    v = lambda chave: float((resumo or {}).get(chave, 0) or 0)
    tipos = [_tipo_exibido(m) for m in movimentos or []]
    vendas = tipos.count("VENDA")
    fiados = tipos.count("RECEBIMENTO_FIADO")
    sangrias = tipos.count("SANGRIA")
    contas = tipos.count("PAGAMENTO")
    nota_entrou = _plural(vendas, "venda", "vendas")
    if fiados:
        nota_entrou += " + " + _plural(fiados, "pagamento de fiado", "pagamentos de fiado")
    nota_saiu = _plural(sangrias, "sangria", "sangrias")
    if contas or v("contas_pagas_caixa") >= 0.01:
        nota_saiu += " · " + _plural(contas, "conta paga", "contas pagas")
    return {
        "abertura": v("saldo_inicial"),
        "entrou": sum(f[2] for f in fatias_formas(resumo)),
        "nota_entrou": nota_entrou,
        "saiu": v("sangrias") + v("contas_pagas_caixa"),
        "nota_saiu": nota_saiu,
        "gaveta": v("total_previsto"),
    }


def texto_diferenca(esperado, contado_texto):
    """("Faltou R$ 2,00", "erro") / ("Sobrou ...", "alerta") / ("Bateu
    certinho", "sucesso"); ("—", "neutro") enquanto nao digitou."""
    try:
        contado = ler_moeda(contado_texto)
    except ValueError:
        return "—", "neutro"
    diferenca = round(contado - esperado, 2)
    if abs(diferenca) < 0.01:
        return "Bateu certinho", "sucesso"
    if diferenca < 0:
        return f"Faltou {formatar_moeda(-diferenca)}", "erro"
    return f"Sobrou {formatar_moeda(diferenca)}", "alerta"


def _hora_movimento(texto):
    """'2026-11-05T10:42:00' -> '10:42' (o turno e' de no maximo 24h)."""
    texto = str(texto or "").replace("T", " ")
    return texto[11:16] if len(texto) >= 16 else texto


def _limpar(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _limpar(item.layout())


def _buscar_dados_caixa(com_resumo=True):
    """Roda na worker thread -- caixa_aberto() + resumo_caixa() +
    listar_movimentos_caixa(), as 3 chamadas que Caixa.carregar()
    precisa. caixa_aberto() precisa vir primeiro (movimentos depende
    do id dele, e' o que decide se tem caixa aberto) -- as outras 2
    dependem so' desse resultado, nao uma da outra, entao disparam
    juntas."""
    caixa = caixa_aberto()

    if caixa is None:
        return caixa, None, []

    # Vendedor nao ve totais (backend responde 403 no resumo)
    if not com_resumo:
        return caixa, {}, listar_movimentos_caixa(caixa["id"])

    resumo, movimentos = em_paralelo(
        (resumo_caixa,), (listar_movimentos_caixa, caixa["id"])
    )

    return caixa, resumo or {}, movimentos


class Caixa(QWidget):

    def __init__(self):
        super().__init__()

        self._carregando = False

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self.paginas = QStackedWidget()
        raiz.addWidget(self.paginas)

        self.pagina_sem_caixa = self._criar_pagina_sem_caixa()
        self.pagina_com_caixa = self._criar_pagina_com_caixa()

        self.paginas.addWidget(self.pagina_sem_caixa)
        self.paginas.addWidget(self.pagina_com_caixa)

        self.carregar()

    # ======================================
    # PÁGINA · SEM CAIXA ABERTO
    # ======================================

    def _criar_pagina_sem_caixa(self):

        pagina = QWidget()

        layout = QVBoxLayout(pagina)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        icone = QLabel()
        icone.setAlignment(Qt.AlignCenter)
        icone.setFixedSize(72, 72)
        icone.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA};
            border-radius:36px;
        """)
        icone.setPixmap(icone_pixmap("lock", cor=tokens.PRIMARIA, tamanho=30))

        titulo = QLabel("Nenhum caixa aberto")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_XL}px; font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            "Abra o caixa para liberar o Frente de Caixa e "
            "começar a registrar vendas."
        )
        subtitulo.setAlignment(Qt.AlignCenter)
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(f"""
            font-size:{tokens.TAMANHO_SM}px; color:{tokens.TEXTO_SECUNDARIO};
        """)
        subtitulo.setFixedWidth(360)

        self.bt_abrir = BotaoSucesso("Abrir Caixa", icone_nome="wallet")
        self.bt_abrir.setFixedWidth(200)
        self.bt_abrir.setMinimumHeight(46)
        self.bt_abrir.clicked.connect(self.abrir_caixa)

        layout.addWidget(icone, alignment=Qt.AlignHCenter)
        layout.addWidget(titulo)
        layout.addWidget(subtitulo, alignment=Qt.AlignHCenter)
        layout.addSpacing(8)
        layout.addWidget(self.bt_abrir, alignment=Qt.AlignHCenter)

        return pagina

    # ======================================
    # PÁGINA · CAIXA ABERTO
    # ======================================

    def _criar_pagina_com_caixa(self):
        """Vertex 2.0 (protótipo Caixa2): título claro com as ações, 4
        números do turno, 'Entrou por forma', movimentos e a conferência
        da gaveta antes de fechar."""

        # Vendedor so' abre e faz sangria/suprimento: sem saldo nem
        # conferencia (quem fecha precisa conferir, ver caixa.fechar)
        self._ve_totais = (
            api.usuario_tem_permissao("financeiro.ver")
            or api.usuario_tem_permissao("caixa.fechar")
        )
        self._esperado = 0.0

        pagina = QScrollArea()
        pagina.setWidgetResizable(True)
        pagina.setFrameShape(QFrame.NoFrame)
        conteudo = QWidget()
        conteudo.setStyleSheet(f"background:{tokens.FUNDO};")
        pagina.setWidget(conteudo)

        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(18)

        # ---- titulo + acoes
        topo = QHBoxLayout()
        topo.setSpacing(8)
        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(4)
        self.lbl_status = _rotulo("Caixa aberto", 28, tokens.TEXTO, 700, titulo=True)
        self.lbl_abertura = _rotulo("", 15, tokens.TEXTO_SECUNDARIO)
        col_titulo.addWidget(self.lbl_status)
        col_titulo.addWidget(self.lbl_abertura)
        topo.addLayout(col_titulo, stretch=1)

        self.bt_suprimento = BotaoSecundario("+ Suprimento")
        self.bt_suprimento.setToolTip("Colocar dinheiro na gaveta (ex.: troco extra)")
        self.bt_suprimento.clicked.connect(self.suprimento)
        self.bt_sangria = BotaoSecundario("− Sangria")
        self.bt_sangria.setToolTip("Tirar dinheiro da gaveta (ex.: levar ao cofre)")
        self.bt_sangria.clicked.connect(self.sangria)
        self.bt_encerrar = BotaoPerigo("Fechar caixa")
        self.bt_encerrar.clicked.connect(self.fechar_caixa)
        self.bt_encerrar.setVisible(api.usuario_tem_permissao("caixa.fechar"))
        for bt in (self.bt_suprimento, self.bt_sangria, self.bt_encerrar):
            bt.setMinimumHeight(44)
            topo.addWidget(bt, 0, Qt.AlignVCenter)
        topo.addWidget(botao_olho(tokens.TEXTO_SECUNDARIO, tamanho=40, tamanho_icone=20), 0, Qt.AlignVCenter)
        layout.addLayout(topo)

        # ---- 4 numeros do turno
        self.secao_kpis = QWidget()
        kpis = QHBoxLayout(self.secao_kpis)
        kpis.setContentsMargins(0, 0, 0, 0)
        kpis.setSpacing(14)
        self.kpi_abertura = _Numero("Abertura")
        self.kpi_entrou = _Numero("Entrou")
        self.kpi_saiu = _Numero("Saiu")
        self.kpi_gaveta = _Numero("Esperado na gaveta")
        self.kpi_gaveta.setStyleSheet(f"""
            QFrame#numeroInicio {{ background:{tokens.SIDEBAR}; border:1px solid {tokens.SIDEBAR};
                                   border-radius:{tokens.RADIUS_LG}px; }}
        """)
        rotulo_gaveta = self.kpi_gaveta.findChildren(QLabel)[0]
        rotulo_gaveta.setStyleSheet(rotulo_gaveta.styleSheet().replace(tokens.TEXTO_SECUNDARIO, tokens.TEXTO_SIDEBAR))
        self.kpi_gaveta.lbl_valor.setStyleSheet(
            self.kpi_gaveta.lbl_valor.styleSheet().replace(f"color:{tokens.TEXTO};", "color:#FFFFFF;"))
        self.lbl_total_previsto = self.kpi_gaveta.lbl_valor
        for kpi in (self.kpi_abertura, self.kpi_entrou, self.kpi_saiu, self.kpi_gaveta):
            kpis.addWidget(kpi, stretch=1)
        self.secao_kpis.setVisible(self._ve_totais)
        layout.addWidget(self.secao_kpis)

        # ---- entrou por forma + movimentos
        meio = QHBoxLayout()
        meio.setSpacing(16)

        self.cartao_formas = _cartao("cartaoFormas")
        self.cartao_formas.setMinimumWidth(340)
        lay_formas = QVBoxLayout(self.cartao_formas)
        lay_formas.setContentsMargins(20, 20, 20, 20)
        lay_formas.setSpacing(14)
        lay_formas.addWidget(_rotulo("Entrou por forma", 17, tokens.TEXTO, 700))
        self.lista_formas = QVBoxLayout()
        self.lista_formas.setSpacing(14)
        lay_formas.addLayout(self.lista_formas)
        nota = _rotulo("Fiado não entra na gaveta: aparece separado no fechamento.",
                       tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO)
        nota.setWordWrap(True)
        lay_formas.addWidget(nota)
        lay_formas.addStretch()
        self.cartao_formas.setVisible(self._ve_totais)
        meio.addWidget(self.cartao_formas, stretch=2)

        cartao_movs = _cartao("cartaoMovimentos")
        lay_movs = QVBoxLayout(cartao_movs)
        lay_movs.setContentsMargins(20, 16, 20, 16)
        lay_movs.setSpacing(0)
        cab_movs = QHBoxLayout()
        cab_movs.addWidget(_rotulo("Movimentos do turno", 17, tokens.TEXTO, 700))
        cab_movs.addStretch()
        self.bt_caixas_anteriores = BotaoSecundario("Caixas anteriores", icone_nome="calendar")
        self.bt_caixas_anteriores.setMinimumHeight(32)
        self.bt_caixas_anteriores.clicked.connect(self.abrir_caixas_anteriores)
        self.bt_caixas_anteriores.setVisible(api.usuario_tem_permissao("financeiro.ver"))
        self.bt_atualizar_historico = BotaoSecundario("Atualizar", icone_nome="refresh-cw")
        self.bt_atualizar_historico.setMinimumHeight(32)
        self.bt_atualizar_historico.clicked.connect(self.carregar)
        cab_movs.addWidget(self.bt_caixas_anteriores)
        cab_movs.addWidget(self.bt_atualizar_historico)
        lay_movs.addLayout(cab_movs)
        lay_movs.addSpacing(8)
        self.lista_movimentos = QVBoxLayout()
        self.lista_movimentos.setSpacing(0)
        lay_movs.addLayout(self.lista_movimentos)
        self.lbl_sem_movimentos = _rotulo(
            "Nenhuma movimentação ainda neste turno.\n"
            "Vendas, suprimentos e sangrias aparecem aqui.",
            tokens.TAMANHO_SM, tokens.TEXTO_TERCIARIO)
        self.lbl_sem_movimentos.setAlignment(Qt.AlignCenter)
        self.lbl_sem_movimentos.setMinimumHeight(120)
        self.lbl_sem_movimentos.setVisible(False)
        lay_movs.addWidget(self.lbl_sem_movimentos)
        lay_movs.addStretch()
        meio.addWidget(cartao_movs, stretch=3)
        layout.addLayout(meio)

        # ---- conferir a gaveta
        self.cartao_conferir = _cartao("cartaoConferir")
        conf = QHBoxLayout(self.cartao_conferir)
        conf.setContentsMargins(20, 20, 20, 20)
        conf.setSpacing(16)
        col_txt = QVBoxLayout()
        col_txt.setSpacing(4)
        col_txt.addWidget(_rotulo("Conferir a gaveta antes de fechar", 17, tokens.TEXTO, 700))
        explica = _rotulo("Conte o dinheiro e digite aqui. O Vertex mostra se sobrou ou faltou.",
                          tokens.TAMANHO_MD, tokens.TEXTO_SECUNDARIO)
        explica.setWordWrap(True)
        col_txt.addWidget(explica)
        conf.addLayout(col_txt, stretch=1)

        def campo(rotulo, widget):
            col = QVBoxLayout()
            col.setSpacing(4)
            col.addWidget(_rotulo(rotulo, tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO))
            widget.setFixedHeight(44)
            widget.setMinimumWidth(150)
            col.addWidget(widget)
            conf.addLayout(col)

        self.lbl_conf_esperado = QLabel("R$ 0,00")
        self.lbl_conf_esperado.setStyleSheet(
            f"background:{tokens.FUNDO}; border-radius:9px; padding:0 12px; "
            f"color:{tokens.TEXTO}; font-size:17px; font-weight:700;")
        campo("Esperado na gaveta", self.lbl_conf_esperado)
        self.campo_contado = QLineEdit()
        self.campo_contado.setPlaceholderText("R$ 0,00")
        self.campo_contado.setStyleSheet(
            f"QLineEdit {{ background:{tokens.CARD}; border:1px solid {tokens.BORDA_FORTE}; "
            f"border-radius:9px; padding:0 12px; color:{tokens.TEXTO}; font-size:17px; font-weight:700; }}")
        self.campo_contado.textChanged.connect(self._atualizar_diferenca)
        campo("Contado", self.campo_contado)
        self.lbl_diferenca = QLabel("—")
        campo("Diferença", self.lbl_diferenca)
        self._atualizar_diferenca()
        self.cartao_conferir.setVisible(self._ve_totais)
        layout.addWidget(self.cartao_conferir)
        layout.addStretch()

        return pagina

    def _atualizar_diferenca(self, *_):
        texto, variante = texto_diferenca(self._esperado, self.campo_contado.text())
        fundo, cor = Badge.variantes()[variante]
        if variante == "neutro":
            fundo, cor = tokens.FUNDO, tokens.TEXTO_SECUNDARIO
        privacidade.definir_texto(self.lbl_diferenca, texto)
        self.lbl_diferenca.setStyleSheet(
            f"background:{fundo}; border-radius:9px; padding:0 12px; "
            f"color:{cor}; font-size:17px; font-weight:700;")


    # ======================================
    # CARREGAR DADOS
    # ======================================

    def carregar(self):

        if self._carregando:
            return
        self._carregando = True
        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            _buscar_dados_caixa,
            self._ve_totais,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        self.bt_abrir.setEnabled(not carregando)
        self.bt_suprimento.setEnabled(not carregando)
        self.bt_sangria.setEnabled(not carregando)
        self.bt_encerrar.setEnabled(not carregando)
        self.bt_atualizar_historico.setEnabled(not carregando)

    def _ao_carregar_sucesso(self, resultado):
        try:
            caixa, resumo, movimentos = resultado

            if caixa is None:
                self.paginas.setCurrentWidget(self.pagina_sem_caixa)
                return

            resumo = resumo or {}

            tempo = _tempo_aberto(caixa.get("data_abertura"))
            self.lbl_abertura.setText(
                _texto_abertura(caixa.get("data_abertura")) + (f" · {tempo}" if tempo else "")
            )

            if self._ve_totais:
                k = numeros_caixa(resumo, movimentos)
                self.kpi_abertura.definir(formatar_moeda(k["abertura"]), "Troco do começo do dia")
                self.kpi_entrou.definir(formatar_moeda(k["entrou"]), k["nota_entrou"])
                self.kpi_saiu.definir(formatar_moeda(k["saiu"]), k["nota_saiu"])
                self.kpi_gaveta.definir(formatar_moeda(k["gaveta"]), "Só dinheiro vivo",
                                        tokens.TEXTO_SIDEBAR)
                self._esperado = k["gaveta"]
                privacidade.definir_texto(self.lbl_conf_esperado, formatar_moeda(k["gaveta"]))
                self._atualizar_diferenca()
                self._atualizar_formas(resumo)

            self.carregar_movimentos(movimentos)

            self.paginas.setCurrentWidget(self.pagina_com_caixa)
        except Exception as erro:
            self._ao_carregar_erro(erro)

    def _atualizar_formas(self, resumo):
        _limpar(self.lista_formas)
        linhas = formas_entrada(resumo)
        for rotulo, forma, valor, pct in linhas:
            linha = QVBoxLayout()
            linha.setSpacing(6)
            topo = QHBoxLayout()
            topo.addWidget(_rotulo(rotulo, tokens.TAMANHO_MD, tokens.TEXTO, 600))
            topo.addStretch()
            lbl_valor = _rotulo("", tokens.TAMANHO_MD, tokens.TEXTO, 700)
            privacidade.definir_texto(lbl_valor, formatar_moeda(valor))
            topo.addWidget(lbl_valor)
            linha.addLayout(topo)
            barra = QProgressBar()
            barra.setRange(0, 100)
            barra.setValue(pct)
            barra.setTextVisible(False)
            barra.setFixedHeight(10)
            barra.setStyleSheet(f"""
                QProgressBar {{ background:{tokens.FUNDO}; border:none; border-radius:5px; }}
                QProgressBar::chunk {{ background:{cor_forma_pagamento(forma)}; border-radius:5px; }}
            """)
            linha.addWidget(barra)
            self.lista_formas.addLayout(linha)
        if not linhas:
            self.lista_formas.addWidget(
                _rotulo("Nada entrou ainda neste turno.", tokens.TAMANHO_MD, tokens.TEXTO_TERCIARIO))

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar o caixa.\n{erro}"
        )

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    def carregar_movimentos(self, movimentos):

        movimentos = sorted(
            movimentos,
            key=lambda m: m.get("data", ""),
            reverse=True,
        )

        _limpar(self.lista_movimentos)
        self.lbl_sem_movimentos.setVisible(not movimentos)

        for mov in movimentos:
            tipo = _tipo_exibido(mov)
            forma = mov.get("forma_pagamento")
            nome_forma = "Fiado" if forma == "PRAZO" else NOMES_FORMA_PAGAMENTO.get(forma, forma or "")

            linha = QFrame()
            linha.setObjectName("linhaMov")
            linha.setStyleSheet(f"QFrame#linhaMov {{ background:transparent; border:none; "
                                f"border-top:1px solid {tokens.BORDA}; }}")
            h = QHBoxLayout(linha)
            h.setContentsMargins(0, 10, 0, 10)
            h.setSpacing(12)
            hora = _rotulo(_hora_movimento(mov.get("data", "")), tokens.TAMANHO_MD, tokens.TEXTO_SECUNDARIO)
            hora.setFixedWidth(46)
            h.addWidget(hora)
            pill = _pill_tipo_movimento(tipo)
            pill.setFixedWidth(150)
            h.addWidget(pill)
            descricao = _descricao_movimento(mov, tipo)
            if nome_forma and tipo not in _TIPOS_SO_FIADO:
                descricao = f"{descricao} · {nome_forma}" if descricao else nome_forma
            lbl_desc = _rotulo(descricao, tokens.TAMANHO_MD, tokens.TEXTO)
            lbl_desc.setWordWrap(True)
            h.addWidget(lbl_desc, stretch=1)
            h.addWidget(_celula_valor_movimento(tipo, formatar_moeda(mov.get("valor", 0))))
            self.lista_movimentos.addWidget(linha)


    # ======================================
    # AÇÕES
    # ======================================

    def abrir_caixas_anteriores(self):
        from telas.caixas_anteriores import CaixasAnterioresDialog
        CaixasAnterioresDialog(parent=self).exec()

    def abrir_caixa(self):

        janela = AbrirCaixaWindow()

        if janela.exec() != QDialog.Accepted:
            return

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            abrir_caixa,
            janela.saldo,
            ao_sucesso=self._ao_abrir_caixa_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_abrir_caixa_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.warning(self, "Erro", erro)

    def _ao_mutacao_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_mutacao_finalizada(self):
        # se o sucesso da mutacao ja disparou carregar() de novo (abrir/
        # sangria/suprimento fazem isso), esse carregar() ja marcou
        # self._carregando=True antes de chegar aqui -- deixa ele mesmo
        # reabilitar os controles quando terminar, senao reabilitava
        # cedo demais (no meio do reload que ele proprio disparou)
        if not self._carregando:
            self._definir_controles_carregando(False)

    def fechar_caixa(self):

        janela = FecharCaixaWindow()

        if janela.exec() != QDialog.Accepted:
            return

        QMessageBox.information(
            self,
            "Sucesso",
            "Caixa fechado com sucesso!",
        )

        self.carregar()

    def sangria(self):

        janela = SangriaWindow()

        if janela.exec() != QDialog.Accepted:
            return

        dados = janela.dados

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            criar_sangria,
            dados["valor"],
            dados["descricao"],
            ao_sucesso=self._ao_movimento_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def suprimento(self):

        janela = SuprimentoWindow()

        if janela.exec() != QDialog.Accepted:
            return

        dados = janela.dados

        self._definir_controles_carregando(True)

        rodar_em_thread(
            self,
            criar_suprimento,
            dados["valor"],
            dados["descricao"],
            ao_sucesso=self._ao_movimento_sucesso,
            ao_erro=self._ao_mutacao_erro,
            ao_finalizar=self._ao_mutacao_finalizada,
        )

    def _ao_movimento_sucesso(self, response):
        if response.status_code == 200:
            self.carregar()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", erro)
