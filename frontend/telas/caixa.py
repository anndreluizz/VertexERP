from datetime import datetime

from telas.suprimento import SuprimentoWindow
from telas.sangria import SangriaWindow
from telas.abrir_caixa import AbrirCaixaWindow, quando, troco_que_ficou
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
    QPushButton,
)

from services.caixa_service import (
    caixa_aberto,
    abrir_caixa,
    resumo_caixa,
    listar_movimentos_caixa,
    historico_caixa,
)

from services.movimento_caixa_service import (
    criar_sangria,
    criar_suprimento,
)

from design import tokens
from design.animations import contar
from design.icons import icone, icone_pixmap
from design.lista import FaixaAtencao
from design.privacidade import botao_olho, privacidade
from design.widgets import Badge, BotaoPerigo, BotaoSecundario, BotaoSucesso, cor_forma_pagamento
from services.worker import rodar_em_thread, em_paralelo
from services import api
from telas.relatorios import NOMES_FORMA_PAGAMENTO
from telas.inicio import _cartao, _rotulo
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


def _minutos_aberto(texto, agora=None):
    """Minutos desde a abertura (0 se a data nao for valida)."""
    try:
        dt = datetime.fromisoformat(str(texto).replace("T", " ")[:19])
    except ValueError:
        return 0
    return max(0, int(((agora or datetime.now()) - dt).total_seconds() // 60))


def _tempo_aberto(texto, agora=None):
    """"há 2h45" / "há 35 min" desde a abertura -- ajuda a ver de longe o
    caixa chegando nas 24h (depois disso ele bloqueia as vendas)."""
    try:
        datetime.fromisoformat(str(texto).replace("T", " ")[:19])
    except ValueError:
        return ""
    minutos = _minutos_aberto(texto, agora)
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


# ícone do círculo de cada tipo de movimento na lista
_ICONE_TIPO = {
    "VENDA": "shopping-cart",
    "SUPRIMENTO": "arrow-up",
    "SANGRIA": "arrow-down",
    "RECEBIMENTO_FIADO": "wallet",
    "ESTORNO": "refresh-cw",
    "VENDA_FIADO": "credit-card",
    "ESTORNO_FIADO": "refresh-cw",
    "PAGAMENTO": "file-text",
}

# entra (+) ou sai (−) do dinheiro; venda/estorno no fiado nao mexe na gaveta
_ENTRA = ("VENDA", "SUPRIMENTO", "RECEBIMENTO_FIADO")
_SAI = ("SANGRIA", "ESTORNO", "PAGAMENTO")

# filtros da lista de movimentos: (rotulo, tipos exibidos); None = todos
FILTROS_MOVIMENTO = [
    ("Todos", None),
    ("Vendas", ("VENDA",)),
    ("Sangrias e suprimentos", ("SANGRIA", "SUPRIMENTO")),
    ("Fiado", ("VENDA_FIADO", "ESTORNO_FIADO", "RECEBIMENTO_FIADO")),
    ("Estornos", ("ESTORNO",)),
    ("Contas pagas", ("PAGAMENTO",)),
]

# aviso "Atenção hoje" quando o caixa passa de 20h aberto (as vendas bloqueiam
# com 24h, ver CaixaResponse.vencido no backend)
LIMITE_AVISO_MINUTOS = 20 * 60

_DIAS_SEMANA = ["SEGUNDA", "TERÇA", "QUARTA", "QUINTA", "SEXTA", "SÁBADO", "DOMINGO"]
_MESES = [
    "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
    "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
]


def filtrar_movimentos(movimentos, tipos):
    """Movimentos cujo tipo exibido esta em `tipos` (None = todos)."""
    if tipos is None:
        return list(movimentos)
    return [m for m in movimentos if _tipo_exibido(m) in tipos]


def _texto_valor_movimento(tipo, valor):
    texto = formatar_moeda(abs(float(valor or 0)))
    if tipo in _ENTRA:
        return f"+ {texto}"
    if tipo in _SAI:
        return f"− {texto}"
    return texto


def saudacao(agora=None):
    hora = (agora or datetime.now()).hour
    if hora < 12:
        return "Bom dia"
    if hora < 18:
        return "Boa tarde"
    return "Boa noite"


def data_por_extenso(agora=None):
    """'DOMINGO · 15 DE NOVEMBRO' (sem depender do locale do Windows)."""
    agora = agora or datetime.now()
    return f"{_DIAS_SEMANA[agora.weekday()]} · {agora.day} DE {_MESES[agora.month - 1]}"


class _KpiCaixa(QFrame):
    """Cartão de número do turno: rótulo + ícone, valor grande (conta até o
    valor) e uma nota. `escuro` é o 'Esperado na gaveta' (mesmo azul-escuro do
    resumo do Pagamento e do total do PDV)."""

    _TONS = {
        "pri": (tokens.PRIMARIA_CLARA, tokens.PRIMARIA),
        "ok": (tokens.SUCESSO_CLARO, tokens.SUCESSO),
        "erro": (tokens.ERRO_CLARO, tokens.ERRO),
    }

    def __init__(self, rotulo, icone_nome, tom, escuro=False):
        super().__init__()

        self._escuro = escuro
        self.setObjectName("kpiCaixa")
        self.setMinimumHeight(108)

        fundo = tokens.SIDEBAR if escuro else tokens.CARD
        self.setStyleSheet(f"""
            QFrame#kpiCaixa {{ background:{fundo}; border:1px solid {tokens.SIDEBAR if escuro else tokens.BORDA};
                               border-radius:{tokens.RADIUS_LG}px; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(2)

        topo = QHBoxLayout()
        topo.addWidget(_rotulo(
            rotulo, tokens.TAMANHO_SM,
            tokens.TEXTO_SIDEBAR if escuro else tokens.TEXTO_SECUNDARIO, 600,
        ))
        topo.addStretch()

        chip = QLabel()
        chip.setFixedSize(32, 32)
        chip.setAlignment(Qt.AlignCenter)
        fundo_chip, cor_icone = (
            (tokens.SIDEBAR_HOVER, tokens.TEXTO_CLARO) if escuro else self._TONS[tom]
        )
        chip.setPixmap(icone(icone_nome, cor=cor_icone, tamanho=17).pixmap(17, 17))
        chip.setStyleSheet(
            f"background:{fundo_chip}; border:none; border-radius:{tokens.RADIUS_SM + 1}px;"
        )
        topo.addWidget(chip)
        layout.addLayout(topo)

        self.lbl_valor = _rotulo(
            "—", 26, tokens.TEXTO_CLARO if escuro else tokens.TEXTO, 700, titulo=True,
        )
        layout.addWidget(self.lbl_valor)

        self.lbl_nota = _rotulo("", tokens.TAMANHO_XS, self._cor_nota_padrao())
        layout.addWidget(self.lbl_nota)

    def _cor_nota_padrao(self):
        return tokens.TEXTO_SIDEBAR if self._escuro else tokens.TEXTO_TERCIARIO

    def definir(self, valor, nota, cor_nota=None):
        contar(self.lbl_valor, valor)
        privacidade.definir_texto(self.lbl_nota, nota)
        self.lbl_nota.setStyleSheet(
            f"background:transparent; border:none; color:{cor_nota or self._cor_nota_padrao()}; "
            f"font-size:{tokens.TAMANHO_XS}px;"
        )


def _limpar(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            # tira da tela ja': so' o deleteLater deixava a linha antiga
            # desenhada ate' o proximo ciclo (linha "fantasma" ao filtrar)
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
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
        """Caixa fechado: cartão de boas-vindas com o botão de abrir e, pra
        quem vê o histórico, como foi o último fechamento."""

        pagina = QWidget()

        raiz = QVBoxLayout(pagina)
        raiz.setContentsMargins(24, 28, 24, 24)

        centro = QHBoxLayout()
        centro.addStretch()

        coluna = QVBoxLayout()
        coluna.setSpacing(16)

        hero = QFrame()
        hero.setObjectName("heroCaixa")
        hero.setFixedWidth(820)
        hero.setMinimumHeight(280)
        hero.setStyleSheet(f"""
            QFrame#heroCaixa {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {tokens.SIDEBAR}, stop:1 {tokens.PRIMARIA});
                border:none; border-radius:{tokens.RADIUS_LG + 6}px;
            }}
        """)

        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(44, 36, 44, 36)
        hero_layout.setSpacing(32)

        bolha = QLabel()
        bolha.setFixedSize(120, 120)
        bolha.setAlignment(Qt.AlignCenter)
        bolha.setPixmap(icone_pixmap("wallet", cor="#FFFFFF", tamanho=54))
        bolha.setStyleSheet("background:rgba(255,255,255,0.14); border:none; border-radius:60px;")
        hero_layout.addWidget(bolha, 0, Qt.AlignVCenter)

        textos = QVBoxLayout()
        textos.setSpacing(6)
        textos.addStretch()

        self.lbl_data_hoje = _rotulo("", tokens.TAMANHO_XS, "rgba(255,255,255,0.7)", 700)
        self.lbl_saudacao = _rotulo("", 34, "#FFFFFF", 700, titulo=True)
        subtitulo = _rotulo(
            "O caixa está fechado. Abra para liberar a Frente de Caixa e "
            "começar a registrar vendas.",
            tokens.TAMANHO_MD, "rgba(255,255,255,0.8)",
        )
        subtitulo.setWordWrap(True)

        textos.addWidget(self.lbl_data_hoje)
        textos.addWidget(self.lbl_saudacao)
        textos.addWidget(subtitulo)
        textos.addSpacing(14)

        botoes = QHBoxLayout()
        botoes.setSpacing(12)

        self.bt_abrir = BotaoSucesso("Abrir Caixa", icone_nome="wallet")
        self.bt_abrir.setFixedSize(190, 52)
        self.bt_abrir.clicked.connect(self.abrir_caixa)
        botoes.addWidget(self.bt_abrir)

        self.bt_anteriores_vazio = QPushButton("  Caixas anteriores")
        self.bt_anteriores_vazio.setIcon(icone("calendar", cor="#FFFFFF", tamanho=18))
        self.bt_anteriores_vazio.setFixedHeight(52)
        self.bt_anteriores_vazio.setCursor(Qt.PointingHandCursor)
        self.bt_anteriores_vazio.setStyleSheet(f"""
            QPushButton {{
                background:rgba(255,255,255,0.12); color:#FFFFFF;
                border:1px solid rgba(255,255,255,0.35); border-radius:{tokens.RADIUS_SM + 2}px;
                padding:0 20px; font-weight:600; font-size:{tokens.TAMANHO_BASE}px;
            }}
            QPushButton:hover {{ background:rgba(255,255,255,0.22); }}
        """)
        self.bt_anteriores_vazio.clicked.connect(self.abrir_caixas_anteriores)
        self.bt_anteriores_vazio.setVisible(api.usuario_tem_permissao("financeiro.ver"))
        botoes.addWidget(self.bt_anteriores_vazio)
        botoes.addStretch()

        textos.addLayout(botoes)
        textos.addStretch()
        hero_layout.addLayout(textos, 1)

        coluna.addWidget(hero)

        # ---- último fechamento (só pra quem vê o histórico, e quando há um)
        self.secao_ultimo = QWidget()
        lay_ultimo = QVBoxLayout(self.secao_ultimo)
        lay_ultimo.setContentsMargins(0, 0, 0, 0)
        lay_ultimo.setSpacing(10)
        lay_ultimo.addWidget(_rotulo("ÚLTIMO FECHAMENTO", tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO, 700))

        tiles = QHBoxLayout()
        tiles.setSpacing(14)
        self._tiles_ultimo = []
        for rotulo, icone_nome in (
            ("Fechado", "lock"), ("Troco que ficou", "dollar-sign"), ("Conferência", "check"),
        ):
            tile, lbl_valor, lbl_detalhe = self._criar_tile_fechamento(rotulo, icone_nome)
            self._tiles_ultimo.append((lbl_valor, lbl_detalhe))
            tiles.addWidget(tile)
        lay_ultimo.addLayout(tiles)

        self.secao_ultimo.hide()
        coluna.addWidget(self.secao_ultimo)
        coluna.addStretch()

        centro.addLayout(coluna)
        centro.addStretch()
        raiz.addLayout(centro)
        raiz.addStretch()

        return pagina

    def _criar_tile_fechamento(self, rotulo, icone_nome):

        tile = QFrame()
        tile.setObjectName("tileFechamento")
        tile.setFixedHeight(92)
        tile.setStyleSheet(f"""
            QFrame#tileFechamento {{ background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                                    border-radius:{tokens.RADIUS_LG}px; }}
        """)

        layout = QHBoxLayout(tile)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(14)

        chip = QLabel()
        chip.setFixedSize(44, 44)
        chip.setAlignment(Qt.AlignCenter)
        chip.setPixmap(icone(icone_nome, cor=tokens.PRIMARIA, tamanho=22).pixmap(22, 22))
        chip.setStyleSheet(
            f"background:{tokens.PRIMARIA_CLARA}; border:none; border-radius:{tokens.RADIUS_MD}px;"
        )
        layout.addWidget(chip)

        coluna = QVBoxLayout()
        coluna.setSpacing(0)
        coluna.addStretch()
        coluna.addWidget(_rotulo(rotulo, tokens.TAMANHO_XS, tokens.TEXTO_SECUNDARIO, 600))
        lbl_valor = _rotulo("—", tokens.TAMANHO_LG, tokens.TEXTO, 700)
        lbl_detalhe = _rotulo("", tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO)
        coluna.addWidget(lbl_valor)
        coluna.addWidget(lbl_detalhe)
        coluna.addStretch()
        layout.addLayout(coluna, 1)

        return tile, lbl_valor, lbl_detalhe

    def _preparar_sem_caixa(self):

        self.lbl_data_hoje.setText(data_por_extenso())

        primeiro_nome = api.nome_usuario().split()[0] if api.nome_usuario() else ""
        self.lbl_saudacao.setText(
            f"{saudacao()}, {primeiro_nome}" if primeiro_nome else saudacao()
        )

        self.secao_ultimo.hide()

        # o histórico traz o valor de cada fechamento: só pra quem pode ver
        if api.usuario_tem_permissao("financeiro.ver"):
            rodar_em_thread(
                self, historico_caixa,
                ao_sucesso=self._ao_ultimo_fechamento_sucesso,
                ao_erro=lambda _erro: None,
            )

    def _ao_ultimo_fechamento_sucesso(self, sessoes):

        try:
            sessao = next(s for s in sessoes if s.get("status") != "ABERTO")
        except StopIteration:
            return

        ficou = troco_que_ficou(sessao)
        contado = sessao.get("valor_contado")

        if contado is None:
            conferencia, variante, detalhe = "Não contado", "neutro", "sem valor contado"
        else:
            conferencia, variante = texto_diferenca(
                float(sessao.get("saldo_final") or 0), f"{float(contado):.2f}".replace(".", ","),
            )
            diferenca = round(float(contado) - float(sessao.get("saldo_final") or 0), 2)
            detalhe = f"diferença {formatar_moeda(diferenca)}"

        fechou = str(sessao.get("data_fechamento") or sessao.get("data_abertura") or "")
        quando_fechou = f"{quando(fechou)}, {_hora_movimento(fechou)}"
        quem = f"por {sessao['usuario_nome']}" if sessao.get("usuario_nome") else ""

        cor_conferencia = {
            "sucesso": tokens.SECUNDARIA_HOVER, "erro": tokens.ERRO,
            "alerta": tokens.ALERTA_TEXTO,
        }.get(variante, tokens.TEXTO)

        (v1, d1), (v2, d2), (v3, d3) = self._tiles_ultimo
        v1.setText(quando_fechou)
        d1.setText(quem)
        privacidade.definir_texto(v2, formatar_moeda(ficou))
        d2.setText("na gaveta para hoje")
        privacidade.definir_texto(v3, conferencia)
        v3.setStyleSheet(
            f"background:transparent; border:none; color:{cor_conferencia}; "
            f"font-size:{tokens.TAMANHO_LG}px; font-weight:700;"
        )
        privacidade.definir_texto(d3, detalhe)

        self.secao_ultimo.show()

    # ======================================
    # PÁGINA · CAIXA ABERTO
    # ======================================

    def _criar_pagina_com_caixa(self):
        """Título com selo de tempo e as ações, aviso quando o caixa está
        aberto há muito tempo, 4 números do turno, 'Entrou por forma' e os
        movimentos. A conferência da gaveta fica no Fechar caixa."""

        # Vendedor so' abre e faz sangria/suprimento: sem saldo nem
        # conferencia (quem fecha precisa conferir, ver caixa.fechar)
        self._ve_totais = (
            api.usuario_tem_permissao("financeiro.ver")
            or api.usuario_tem_permissao("caixa.fechar")
        )
        self._esperado = 0.0
        self._movimentos = []
        self._filtro_mov = 0

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

        linha_titulo = QHBoxLayout()
        linha_titulo.setSpacing(12)
        self.lbl_status = _rotulo("Caixa aberto", 28, tokens.TEXTO, 700, titulo=True)
        self.selo_tempo = Badge("Aberto", "sucesso")
        linha_titulo.addWidget(self.lbl_status)
        linha_titulo.addWidget(self.selo_tempo, 0, Qt.AlignVCenter)
        linha_titulo.addStretch()
        col_titulo.addLayout(linha_titulo)

        self.lbl_abertura = _rotulo("", tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO)
        col_titulo.addWidget(self.lbl_abertura)
        topo.addLayout(col_titulo, stretch=1)

        self.bt_suprimento = BotaoSecundario("Suprimento", icone_nome="plus")
        self.bt_suprimento.setToolTip("Colocar dinheiro na gaveta (ex.: troco extra)")
        self.bt_suprimento.clicked.connect(self.suprimento)
        self.bt_sangria = BotaoSecundario("Sangria", icone_nome="arrow-down")
        self.bt_sangria.setToolTip("Tirar dinheiro da gaveta (ex.: levar ao cofre)")
        self.bt_sangria.clicked.connect(self.sangria)
        self.bt_encerrar = BotaoPerigo("Fechar caixa", icone_nome="lock")
        self.bt_encerrar.clicked.connect(self.fechar_caixa)
        self.bt_encerrar.setVisible(api.usuario_tem_permissao("caixa.fechar"))
        for bt in (self.bt_suprimento, self.bt_sangria, self.bt_encerrar):
            bt.setMinimumHeight(42)
            topo.addWidget(bt, 0, Qt.AlignVCenter)
        topo.addWidget(botao_olho(tokens.TEXTO_SECUNDARIO, tamanho=40, tamanho_icone=20), 0, Qt.AlignVCenter)
        layout.addLayout(topo)

        self.faixa_atencao = FaixaAtencao()
        layout.addWidget(self.faixa_atencao)

        # ---- 4 numeros do turno
        self.secao_kpis = QWidget()
        kpis = QHBoxLayout(self.secao_kpis)
        kpis.setContentsMargins(0, 0, 0, 0)
        kpis.setSpacing(14)
        self.kpi_abertura = _KpiCaixa("Abertura", "wallet", "pri")
        self.kpi_entrou = _KpiCaixa("Entrou", "arrow-down", "ok")
        self.kpi_saiu = _KpiCaixa("Saiu", "arrow-up", "erro")
        self.kpi_gaveta = _KpiCaixa("Esperado na gaveta", "dollar-sign", "pri", escuro=True)
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
        lay_formas.setSpacing(12)
        cab_formas = QHBoxLayout()
        cab_formas.addWidget(_rotulo("Entrou por forma", tokens.TAMANHO_LG, tokens.TEXTO, 700))
        cab_formas.addStretch()
        self.lbl_total_entrou = _rotulo("", tokens.TAMANHO_LG, tokens.SECUNDARIA_HOVER, 700)
        cab_formas.addWidget(self.lbl_total_entrou)
        lay_formas.addLayout(cab_formas)
        self.lista_formas = QVBoxLayout()
        self.lista_formas.setSpacing(12)
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
        lay_movs.setSpacing(6)
        cab_movs = QHBoxLayout()
        cab_movs.setSpacing(10)
        cab_movs.addWidget(_rotulo("Movimentos do turno", tokens.TAMANHO_LG, tokens.TEXTO, 700))
        cab_movs.addStretch()
        self.bt_caixas_anteriores = BotaoSecundario("Caixas anteriores", icone_nome="calendar")
        self.bt_caixas_anteriores.setMinimumHeight(34)
        self.bt_caixas_anteriores.clicked.connect(self.abrir_caixas_anteriores)
        self.bt_caixas_anteriores.setVisible(api.usuario_tem_permissao("financeiro.ver"))
        self.bt_atualizar_historico = BotaoSecundario("Atualizar", icone_nome="refresh-cw")
        self.bt_atualizar_historico.setMinimumHeight(34)
        self.bt_atualizar_historico.clicked.connect(self.carregar)
        cab_movs.addWidget(self.bt_caixas_anteriores)
        cab_movs.addWidget(self.bt_atualizar_historico)
        lay_movs.addLayout(cab_movs)

        # filtros (so' aparecem os tipos que existem no turno)
        self._chips_mov = {}
        self._linha_chips = QHBoxLayout()
        self._linha_chips.setSpacing(8)
        for indice, (rotulo, tipos) in enumerate(FILTROS_MOVIMENTO):
            bt = QPushButton(rotulo)
            bt.setFixedHeight(30)
            bt.setCursor(Qt.PointingHandCursor)
            bt.clicked.connect(lambda _=False, i=indice: self._escolher_filtro_movimento(i))
            self._chips_mov[indice] = (bt, rotulo, tipos)
            self._linha_chips.addWidget(bt)
        self._linha_chips.addStretch()
        lay_movs.addLayout(self._linha_chips)
        lay_movs.addSpacing(4)

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
        layout.addStretch()

        return pagina

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
                self._preparar_sem_caixa()
                self.paginas.setCurrentWidget(self.pagina_sem_caixa)
                return

            resumo = resumo or {}

            self._mostrar_abertura(caixa)

            if self._ve_totais:
                k = numeros_caixa(resumo, movimentos)
                self.kpi_abertura.definir(formatar_moeda(k["abertura"]), "Troco do começo do dia")
                self.kpi_entrou.definir(formatar_moeda(k["entrou"]), k["nota_entrou"])
                self.kpi_saiu.definir(formatar_moeda(k["saiu"]), k["nota_saiu"])
                self.kpi_gaveta.definir(formatar_moeda(k["gaveta"]), "Só dinheiro vivo",
                                        tokens.TEXTO_SIDEBAR)
                self._esperado = k["gaveta"]
                self._atualizar_formas(resumo)

            self._movimentos = list(movimentos or [])
            self._aplicar_filtro_movimento()

            self.paginas.setCurrentWidget(self.pagina_com_caixa)
        except Exception as erro:
            self._ao_carregar_erro(erro)

    def _mostrar_abertura(self, caixa):
        """Linha de abertura, selo de tempo e o aviso quando o caixa esta
        perto de bloquear as vendas (24h)."""

        abertura = caixa.get("data_abertura")
        self.lbl_abertura.setText(_texto_abertura(abertura))

        tempo = _tempo_aberto(abertura)
        minutos = _minutos_aberto(abertura)
        vencido = bool(caixa.get("vencido"))
        perto = vencido or minutos >= LIMITE_AVISO_MINUTOS

        self.selo_tempo.setText(f"Aberto {tempo}" if tempo else "Aberto")
        self.selo_tempo.definir_variante("alerta" if perto else "sucesso")

        if vencido:
            texto = "Caixa aberto há mais de 24h: feche para voltar a vender"
        elif perto:
            texto = f"Caixa aberto {tempo}: as vendas bloqueiam com 24h"
        else:
            self.faixa_atencao.definir([])
            return

        pode_fechar = api.usuario_tem_permissao("caixa.fechar")
        self.faixa_atencao.definir([
            (texto, "Fechar caixa" if pode_fechar else None, self.fechar_caixa)
        ])

    def _atualizar_formas(self, resumo):
        _limpar(self.lista_formas)
        linhas = formas_entrada(resumo)
        entram = [l for l in linhas if l[1] != "PRAZO"]
        fiado = [l for l in linhas if l[1] == "PRAZO"]

        privacidade.definir_texto(
            self.lbl_total_entrou, formatar_moeda(sum(l[2] for l in entram))
        )

        if entram:
            # barra unica segmentada: cada forma com a sua cor
            segmentos = QHBoxLayout()
            segmentos.setSpacing(3)
            for rotulo, forma, valor, pct in entram:
                seg = QFrame()
                seg.setFixedHeight(12)
                seg.setStyleSheet(
                    f"background:{cor_forma_pagamento(forma)}; border:none; border-radius:6px;"
                )
                segmentos.addWidget(seg, max(1, int(round(valor * 100))))
            self.lista_formas.addLayout(segmentos)
            self.lista_formas.addSpacing(4)

        for rotulo, forma, valor, pct in entram:
            self.lista_formas.addLayout(self._linha_forma(
                rotulo, f"{pct}%", valor, cor_forma_pagamento(forma), tokens.TEXTO,
            ))

        if fiado:
            divisor = QFrame()
            divisor.setFixedHeight(1)
            divisor.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
            self.lista_formas.addSpacing(4)
            self.lista_formas.addWidget(divisor)
            self.lista_formas.addLayout(self._linha_forma(
                fiado[0][0], "", fiado[0][2], tokens.ALERTA, tokens.ALERTA_TEXTO, anel=True,
            ))

        if not linhas:
            self.lista_formas.addWidget(
                _rotulo("Nada entrou ainda neste turno.", tokens.TAMANHO_MD, tokens.TEXTO_TERCIARIO))

    def _linha_forma(self, rotulo, pct, valor, cor_bolinha, cor_valor, anel=False):

        linha = QHBoxLayout()
        linha.setSpacing(10)

        bolinha = QFrame()
        bolinha.setFixedSize(10, 10)
        bolinha.setStyleSheet(
            f"border:2px dashed {cor_bolinha}; border-radius:5px; background:transparent;"
            if anel else
            f"background:{cor_bolinha}; border:none; border-radius:5px;"
        )
        linha.addWidget(bolinha)
        linha.addWidget(_rotulo(rotulo, tokens.TAMANHO_BASE, tokens.TEXTO, 600))
        linha.addStretch()
        if pct:
            linha.addWidget(_rotulo(pct, tokens.TAMANHO_SM, tokens.TEXTO_TERCIARIO))

        lbl_valor = _rotulo("", tokens.TAMANHO_BASE, cor_valor, 700)
        lbl_valor.setMinimumWidth(110)
        lbl_valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        privacidade.definir_texto(lbl_valor, formatar_moeda(valor))
        linha.addWidget(lbl_valor)

        return linha

    def _ao_carregar_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar o caixa.\n{erro}"
        )

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    def _escolher_filtro_movimento(self, indice):
        self._filtro_mov = indice
        self._aplicar_filtro_movimento()

    def _aplicar_filtro_movimento(self):
        """Contagem em cada filtro, esconde os que nao tem nada e redesenha a lista."""

        movimentos = self._movimentos

        for indice, (bt, rotulo, tipos) in self._chips_mov.items():
            quantos = len(filtrar_movimentos(movimentos, tipos))
            bt.setText(f"{rotulo}   {quantos}")
            bt.setVisible(tipos is None or quantos > 0)

        # o filtro escolhido sumiu (turno recarregado sem esse tipo): volta pra Todos
        if self._chips_mov[self._filtro_mov][0].isHidden():
            self._filtro_mov = 0

        for indice, (bt, rotulo, tipos) in self._chips_mov.items():
            sel = indice == self._filtro_mov
            bt.setStyleSheet(f"""
                QPushButton {{
                    padding:0 14px; border-radius:15px; font-size:{tokens.TAMANHO_XS}px;
                    font-weight:{700 if sel else 600};
                    border:1px solid {tokens.PRIMARIA_CLARA if sel else tokens.BORDA};
                    background:{tokens.PRIMARIA_CLARA if sel else tokens.CARD};
                    color:{tokens.PRIMARIA if sel else tokens.TEXTO_SECUNDARIO};
                }}
                QPushButton:hover {{ background:{tokens.PRIMARIA_CLARA if sel else tokens.FUNDO}; }}
            """)

        self.carregar_movimentos(
            filtrar_movimentos(movimentos, self._chips_mov[self._filtro_mov][2])
        )

    def carregar_movimentos(self, movimentos):

        movimentos = sorted(
            movimentos,
            key=lambda m: m.get("data", ""),
            reverse=True,
        )

        _limpar(self.lista_movimentos)
        self.lbl_sem_movimentos.setVisible(not movimentos)

        for mov in movimentos:
            self.lista_movimentos.addWidget(Caixa._linha_movimento(mov))

    @staticmethod
    def _linha_movimento(mov):

        tipo = _tipo_exibido(mov)
        forma = mov.get("forma_pagamento")
        nome_forma = "Fiado" if forma == "PRAZO" else NOMES_FORMA_PAGAMENTO.get(forma, forma or "")
        rotulo_tipo, variante = _INFO_TIPO_MOVIMENTO.get(
            tipo, (tipo.replace("_", " ").title() if tipo else "—", "neutro")
        )
        fundo_icone, cor_icone = Badge.variantes()[variante]

        linha = QFrame()
        linha.setObjectName("linhaMov")
        linha.setStyleSheet(f"""
            QFrame#linhaMov {{ background:transparent; border:none; border-top:1px solid {tokens.BORDA}; }}
            QFrame#linhaMov:hover {{ background:{tokens.FUNDO}; }}
        """)
        h = QHBoxLayout(linha)
        h.setContentsMargins(4, 10, 4, 10)
        h.setSpacing(12)

        hora = _rotulo(_hora_movimento(mov.get("data", "")), tokens.TAMANHO_SM, tokens.TEXTO_TERCIARIO)
        hora.setFixedWidth(40)
        h.addWidget(hora)

        chip = QLabel()
        chip.setFixedSize(34, 34)
        chip.setAlignment(Qt.AlignCenter)
        chip.setPixmap(icone(_ICONE_TIPO.get(tipo, "file-text"), cor=cor_icone, tamanho=17).pixmap(17, 17))
        chip.setStyleSheet(f"background:{fundo_icone}; border:none; border-radius:17px;")
        h.addWidget(chip)

        coluna = QVBoxLayout()
        coluna.setSpacing(0)
        lbl_desc = _rotulo(
            _descricao_movimento(mov, tipo), tokens.TAMANHO_BASE, tokens.TEXTO, 600,
        )
        lbl_desc.setWordWrap(True)
        sub = rotulo_tipo
        if nome_forma and tipo not in _TIPOS_SO_FIADO:
            sub = f"{rotulo_tipo} · {nome_forma}"
        coluna.addWidget(lbl_desc)
        coluna.addWidget(_rotulo(sub, tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO))
        h.addLayout(coluna, stretch=1)

        lbl_valor = QLabel()
        lbl_valor.setFixedWidth(120)
        lbl_valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        privacidade.definir_texto(lbl_valor, _texto_valor_movimento(tipo, mov.get("valor", 0)))
        lbl_valor.setStyleSheet(
            f"background:transparent; border:none; color:{_cor_valor_movimento(tipo)}; "
            f"font-size:{tokens.TAMANHO_BASE}px; font-weight:700;"
        )
        h.addWidget(lbl_valor)

        return linha


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

    def _esperado_ou_none(self):
        # Vendedor nao ve totais da gaveta: o dialogo fica so' com o formulario
        return self._esperado if self._ve_totais else None

    def sangria(self):

        janela = SangriaWindow(self._esperado_ou_none())

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

        janela = SuprimentoWindow(self._esperado_ou_none())

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
