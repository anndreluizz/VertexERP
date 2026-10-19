import csv

from PySide6.QtWidgets import QMessageBox

from telas.cadastro_cliente import CadastroClienteDialog
from telas.ficha_cliente import FichaClienteDialog

from services.caixa_service import entradas_caixa
from services.cliente_service import listar_clientes, reativar_cliente
from services.preferencias_service import carregar_loja_id
from services.loja_service import listar_lojas
from services.movimento_fiado_service import listar_movimentos
from services.venda_service import listar_vendas
from services import api, cliente_analise

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QShortcut, QKeySequence, QPainter, QColor

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QDialog,
    QComboBox,
    QFileDialog,
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import Avatar, Badge, BotaoPrimario, BotaoSecundario, CampoTexto, Card, CardKPI
from services.worker import rodar_em_thread, em_paralelo
from utils.formatacao import formatar_moeda
from widgets.estado_async import PainelErro, cartoes_esqueleto


# rótulo exibido -> chave interna do filtro
FILTROS = [
    ("Todos", "TODOS"),
    ("Clientes Ativos", "ATIVOS"),
    ("Sem Movimento", "SEM_MOVIMENTO"),
    ("Inadimplentes", "INADIMPLENTES"),
    ("Em Dia", "EM_DIA"),
    ("Bons Pagadores", "BONS_PAGADORES"),
    ("Novos Clientes", "NOVOS"),
    # aba so' deles: divida baixada como perda, fora de todo o resto
    ("Negativados", "NEGATIVADOS"),
]

# icone (lucide) de cada filtro -- nao ha "clock" no pacote baixado,
# "calendar" fica o mais proximo pra "Sem Movimento"
_ICONES_FILTRO = {
    "TODOS": "users",
    "ATIVOS": "user",
    "SEM_MOVIMENTO": "calendar",
    "INADIMPLENTES": "alert-triangle",
    "EM_DIA": "check",
    "BONS_PAGADORES": "star",
    "NOVOS": "user",
    "NEGATIVADOS": "lock",
}

# rótulo exibido -> chave interna da ordenação, na ordem que aparece no combo
ORDENACOES = [
    ("Último Movimento (mais recente primeiro)", "MOVIMENTO_RECENTE"),
    ("Último Movimento (mais antigo primeiro)", "MOVIMENTO_ANTIGO"),
    ("Última Compra", "ULTIMA_COMPRA"),
    ("Maior Compra", "MAIOR_COMPRA"),
    ("Maior Saldo Devedor", "MAIOR_SALDO"),
    ("Nome (A-Z)", "NOME_AZ"),
    ("Nome (Z-A)", "NOME_ZA"),
    ("Cliente Mais Antigo", "CADASTRO_ANTIGO"),
    ("Cliente Mais Novo", "CADASTRO_NOVO"),
]

def _buscar_dados_clientes(loja_id):
    """Roda na worker thread (ver services/worker.py) -- as 3 chamadas
    de rede + a agregacao de carregar() (nenhuma toca widget, so' monta
    dict/soma numero, seguro rodar fora da GUI thread).

    As 3 chamadas nao dependem uma da outra (cada uma busca uma lista
    inteira separada), entao disparam em paralelo em vez de em fila --
    numa conexao com latencia alta (ex.: terminal remoto via VPN), 3
    chamadas sequenciais somam 3x a latencia por chamada; em paralelo
    o tempo total fica perto do da mais lenta das 3."""

    # recebido de fiado e' dinheiro da loja: sai do caixa onde entrou
    # (Caixa.loja_id). Sem loja no combo, usa a loja deste terminal --
    # senao a Filial via os recebimentos da Matriz somados aos dela.
    loja_recebido = loja_id if loja_id is not None else carregar_loja_id()

    clientes, movimentos_fiado, vendas, entradas = em_paralelo(
        (listar_clientes, loja_id),
        (listar_movimentos,),
        (listar_vendas,),
        (entradas_caixa, None, None, loja_recebido),
    )

    movimentos_por_cliente = {}
    for mov in movimentos_fiado:
        cid = mov.get("cliente_id")
        if cid is None:
            continue
        movimentos_por_cliente.setdefault(cid, []).append(mov)

    agregados_por_cliente = {}
    for cliente in clientes:
        agr = cliente_analise.calcular_agregados(
            cliente, movimentos_por_cliente.get(cliente["id"], [])
        )
        agregados_por_cliente[cliente["id"]] = agr
        cliente["saldo_fiado"] = agr["saldo_devedor"]

    vendas_por_cliente = {}
    for venda in vendas:
        cid = venda.get("cliente_id")
        if cid is None:
            continue
        vendas_por_cliente[cid] = (
            vendas_por_cliente.get(cid, 0)
            + float(venda.get("valor_total", 0) or 0)
        )

    recebido_fiado_total = float(entradas.get("fiado_recebido", 0) or 0)

    return (
        clientes,
        agregados_por_cliente,
        vendas_por_cliente,
        recebido_fiado_total,
        movimentos_por_cliente,
    )


def _status_cliente(cliente, agr, prazo_dias):
    """(texto, variante do Badge) do selo de cada linha -- prioridade:
    inativo > inadimplente > perto do limite > devendo > em dia. É o
    que faz quem precisa de atenção saltar aos olhos na lista sem abrir
    a ficha."""

    if cliente.get("negativado"):
        return "Negativado", "erro"

    if not cliente.get("ativo", True):
        return "Inativo", "neutro"

    if not agr:
        return "Sem movimento", "neutro"

    if cliente_analise.eh_inadimplente(agr, prazo_dias):
        return f"Atrasado · {agr.get('dias_em_atraso')} dias", "erro"

    if cliente_analise.eh_em_dia(agr):
        return "Em dia", "sucesso"

    limite = float(cliente.get("limite_credito") or 0)
    if limite > 0 and agr["saldo_devedor"] / limite >= 0.85:
        return "Perto do limite", "alerta"

    return "Fiado em aberto", "info"


def _cor_variante(variante):
    return {
        "erro": tokens.ERRO,
        "alerta": tokens.ALERTA,
        "sucesso": tokens.SECUNDARIA,
        "info": tokens.PRIMARIA,
    }.get(variante, tokens.TEXTO_TERCIARIO)


def _rotulo(texto, tamanho=None, cor=None, peso=400):
    lbl = QLabel(texto)
    lbl.setStyleSheet(f"""
        background:transparent; border:none;
        font-size:{tamanho or tokens.TAMANHO_SM}px;
        font-weight:{peso}; color:{cor or tokens.TEXTO};
    """)
    return lbl


def _limpar_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            # esconde já -- o deleteLater só roda na próxima volta do
            # event loop e o widget velho apareceria por cima do novo
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout():
            _limpar_layout(item.layout())


def _perfil(agr, prazo_dias):
    """'Cliente Frequente' etc. de calcular_pontuacao, sem o emoji do
    começo (pode não renderizar em toda máquina) e sem o 'Cliente'."""
    if not agr:
        return "—"
    texto = cliente_analise.calcular_pontuacao(agr, prazo_dias)
    return texto.partition(" ")[2].replace("Cliente ", "") or texto


def _data_curta(valor):
    return valor.strftime("%d/%m/%Y") if valor else "—"


class _BarraLimite(QWidget):
    """Barrinha fina de quanto do limite de crédito já foi usado --
    pintada à mão (QProgressBar com stylesheet não arredonda o
    preenchimento direito em todo estilo do Qt)."""

    def __init__(self, fracao, cor, parent=None):
        super().__init__(parent)
        self._fracao = max(0.0, min(1.0, fracao))
        self._cor = QColor(cor)
        self.setFixedHeight(6)

    def paintEvent(self, _evento):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        raio = self.height() / 2
        p.setBrush(QColor(tokens.BORDA))
        p.drawRoundedRect(self.rect(), raio, raio)
        if self._fracao > 0:
            cheio = self.rect()
            cheio.setWidth(max(int(self.width() * self._fracao), self.height()))
            p.setBrush(self._cor)
            p.drawRoundedRect(cheio, raio, raio)


class ClienteLinha(QFrame):
    """Uma linha da lista de clientes: avatar, nome/telefone, uso do
    limite, saldo e selo de status. Clique seleciona (mostra no painel
    ao lado); duplo clique ou Enter abre a ficha completa."""

    selecionado = Signal(dict)
    abrir = Signal(dict)

    def __init__(self, cliente, agr, prazo_dias):

        super().__init__()

        self.cliente = cliente
        self.setObjectName("ClienteLinha")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(cliente.get("nome") or "Cliente")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 11, 16, 11)
        layout.setSpacing(14)

        layout.addWidget(Avatar(cliente.get("nome", ""), tamanho=36))

        col_nome = QVBoxLayout()
        col_nome.setSpacing(1)
        linha_nome = QHBoxLayout()
        linha_nome.setSpacing(8)
        linha_nome.addWidget(
            _rotulo(cliente.get("nome") or "", tokens.TAMANHO_MD, peso=600)
        )
        selo = cliente_analise.selo_pagador(agr, prazo_dias)
        if selo:
            linha_nome.addWidget(Badge(*selo))
        linha_nome.addStretch()
        col_nome.addLayout(linha_nome)
        col_nome.addWidget(_rotulo(
            cliente.get("telefone") or "Sem telefone",
            tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO,
        ))
        layout.addLayout(col_nome, stretch=1)

        saldo = float((agr or {}).get("saldo_devedor", 0) or 0)
        texto_status, variante = _status_cliente(cliente, agr, prazo_dias)
        if cliente.get("negativado"):
            # o valor da linha e' o dinheiro perdido (divida baixada)
            saldo = float((agr or {}).get("perdido", 0) or 0)
            texto_status = "Negativado · perdido"

        # uso do limite -- só quem tem limite definido; sem limite, um
        # espaço vazio do mesmo tamanho mantém as colunas alinhadas
        col_limite = QWidget()
        col_limite.setFixedWidth(110)
        col_limite.setStyleSheet("background:transparent;")
        lim_layout = QVBoxLayout(col_limite)
        lim_layout.setContentsMargins(0, 0, 0, 0)
        lim_layout.setSpacing(4)

        limite = float(cliente.get("limite_credito") or 0)
        if limite > 0:
            fracao = max(saldo, 0) / limite
            lim_layout.addWidget(_BarraLimite(fracao, _cor_variante(variante)))
            lim_layout.addWidget(_rotulo(
                f"{fracao:.0%} do limite", tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO
            ))
        layout.addWidget(col_limite)

        # largura fixa pra barra de limite ficar na mesma coluna em toda
        # linha, não importa o tamanho do valor/selo
        col_valor_w = QWidget()
        col_valor_w.setFixedWidth(150)
        col_valor_w.setStyleSheet("background:transparent;")
        col_valor = QVBoxLayout(col_valor_w)
        col_valor.setContentsMargins(0, 0, 0, 0)
        col_valor.setSpacing(3)
        lbl_saldo = _rotulo(formatar_moeda(saldo), tokens.TAMANHO_MD, peso=700)
        lbl_saldo.setAlignment(Qt.AlignRight)
        col_valor.addWidget(lbl_saldo)
        col_valor.addWidget(Badge(texto_status, variante), 0, Qt.AlignRight)
        layout.addWidget(col_valor_w)

        self.definir_selecionado(False)

    def definir_selecionado(self, ativo):

        fundo = tokens.PRIMARIA_CLARA if ativo else "transparent"
        borda = tokens.PRIMARIA if ativo else "transparent"
        self.setStyleSheet(f"""
            #ClienteLinha {{
                background:{fundo};
                border:none;
                border-left:3px solid {borda};
                border-bottom:1px solid {tokens.BORDA};
            }}
            #ClienteLinha:hover {{
                background:{tokens.PRIMARIA_CLARA if ativo else tokens.FUNDO};
            }}
            #ClienteLinha:focus {{ border-left:3px solid {tokens.PRIMARIA}; }}
        """)

    def mousePressEvent(self, event):
        self.selecionado.emit(self.cliente)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.abrir.emit(self.cliente)
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.abrir.emit(self.cliente)
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event):
        # navegar com Tab já seleciona, igual a clicar
        self.selecionado.emit(self.cliente)
        super().focusInEvent(event)


class PainelCliente(Card):
    """Painel à direita da lista com o resumo do cliente selecionado --
    saldo, limite, datas e as últimas movimentações do fiado, mais
    atalhos pras ações do dia a dia (receber, cobrar, abrir a ficha)."""

    abrir_ficha = Signal(dict)
    receber = Signal(dict)
    cobrar = Signal(dict)
    reativar = Signal(dict)

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setFixedWidth(360)

        externo = QVBoxLayout(self)
        externo.setContentsMargins(0, 0, 0, 16)
        externo.setSpacing(12)

        # o resumo rola sozinho e os botões ficam fixos embaixo -- sem
        # isso a altura mínima do painel (todo o conteúdo empilhado)
        # forçava a tela inteira a ficar alta e, em janela menor, o fim
        # da lista de clientes ficava cortado sem conseguir rolar até lá
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rolagem.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        conteudo = QWidget()
        conteudo.setStyleSheet("background:transparent;")
        self._layout = QVBoxLayout(conteudo)
        self._layout.setContentsMargins(20, 20, 20, 4)
        self._layout.setSpacing(16)
        rolagem.setWidget(conteudo)
        externo.addWidget(rolagem, stretch=1)

        self._acoes = QVBoxLayout()
        self._acoes.setContentsMargins(20, 0, 20, 0)
        self._acoes.setSpacing(8)
        externo.addLayout(self._acoes)

        self.mostrar(None)

    def mostrar(self, cliente, agr=None, movimentos=None, prazo_dias=None):

        _limpar_layout(self._layout)
        _limpar_layout(self._acoes)

        if cliente is None:
            vazio = _rotulo(
                "Escolha um cliente na lista pra ver o resumo aqui.",
                tokens.TAMANHO_BASE, tokens.TEXTO_TERCIARIO,
            )
            vazio.setWordWrap(True)
            vazio.setAlignment(Qt.AlignCenter)
            self._layout.addStretch()
            self._layout.addWidget(vazio)
            self._layout.addStretch()
            return

        agr = agr or {}
        prazo_dias = prazo_dias or cliente_analise.PRAZO_INADIMPLENCIA_PADRAO

        # ---- cabeçalho
        topo = QHBoxLayout()
        topo.setSpacing(12)
        topo.addWidget(Avatar(cliente.get("nome", ""), tamanho=48))
        col = QVBoxLayout()
        col.setSpacing(2)
        nome = _rotulo(cliente.get("nome") or "", tokens.TAMANHO_LG, peso=700)
        nome.setWordWrap(True)
        col.addWidget(nome)
        contato = " · ".join(
            p for p in (f"Cód. {cliente.get('id')}", cliente.get("telefone")) if p
        )
        col.addWidget(_rotulo(contato, tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO))
        topo.addLayout(col, stretch=1)
        self._layout.addLayout(topo)

        # ---- saldo em destaque
        saldo = float(agr.get("saldo_devedor", 0) or 0)
        texto_status, variante = _status_cliente(cliente, agr, prazo_dias)

        caixa = QFrame()
        caixa.setStyleSheet(
            f"QFrame {{ background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_MD}px; }}"
        )
        cx = QHBoxLayout(caixa)
        cx.setContentsMargins(16, 14, 16, 14)
        esq = QVBoxLayout()
        esq.setSpacing(2)
        esq.addWidget(
            _rotulo("SALDO DEVEDOR", tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO, 700)
        )
        cor_saldo = tokens.ERRO if variante == "erro" else tokens.TEXTO
        esq.addWidget(_rotulo(formatar_moeda(saldo), tokens.TAMANHO_XXL, cor_saldo, 800))
        cx.addLayout(esq, stretch=1)
        dir_ = QVBoxLayout()
        dir_.setSpacing(4)
        dir_.addWidget(Badge(texto_status, variante), 0, Qt.AlignRight)
        limite = float(cliente.get("limite_credito") or 0)
        lbl_lim = _rotulo(
            f"Limite {formatar_moeda(limite)}" if limite > 0 else "Sem limite definido",
            tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO,
        )
        lbl_lim.setAlignment(Qt.AlignRight)
        dir_.addWidget(lbl_lim)
        cx.addLayout(dir_)
        self._layout.addWidget(caixa)

        # ---- datas
        datas = QGridLayout()
        datas.setHorizontalSpacing(12)
        datas.setVerticalSpacing(6)
        for linha, (rotulo, valor) in enumerate((
            ("Última compra", _data_curta(agr.get("ultima_compra"))),
            ("Último pagamento", _data_curta(agr.get("ultimo_pagamento"))),
            ("Compras no fiado", str(agr.get("qtd_compras", 0))),
            ("Perfil", _perfil(agr, prazo_dias)),
        )):
            datas.addWidget(
                _rotulo(rotulo, tokens.TAMANHO_SM, tokens.TEXTO_SECUNDARIO), linha, 0
            )
            v = _rotulo(valor, tokens.TAMANHO_SM, peso=600)
            v.setAlignment(Qt.AlignRight)
            datas.addWidget(v, linha, 1)
        self._layout.addLayout(datas)

        # ---- últimas movimentações
        self._layout.addWidget(
            _rotulo("ÚLTIMAS MOVIMENTAÇÕES", tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO, 700)
        )

        recentes = sorted(
            movimentos or [],
            key=lambda m: str(m.get("data") or ""),
            reverse=True,
        )[:5]

        if not recentes:
            self._layout.addWidget(_rotulo(
                "Nenhuma movimentação no fiado ainda.",
                tokens.TAMANHO_SM, tokens.TEXTO_TERCIARIO,
            ))

        for mov in recentes:
            pagamento = mov.get("tipo") == "PAGAMENTO"
            linha = QHBoxLayout()
            linha.setSpacing(10)
            col_mov = QVBoxLayout()
            col_mov.setSpacing(0)
            descricao = mov.get("descricao") or (
                "Pagamento" if pagamento else "Compra no fiado"
            )
            lbl_desc = _rotulo(descricao, tokens.TAMANHO_SM, peso=500)
            lbl_desc.setWordWrap(True)
            col_mov.addWidget(lbl_desc)
            col_mov.addWidget(_rotulo(
                _data_curta(cliente_analise._parse_data(mov.get("data"))),
                tokens.TAMANHO_XS, tokens.TEXTO_TERCIARIO,
            ))
            linha.addLayout(col_mov, stretch=1)
            valor = float(mov.get("valor", 0) or 0)
            linha.addWidget(_rotulo(
                f"{'+' if pagamento else '−'} {formatar_moeda(valor)}",
                tokens.TAMANHO_SM,
                tokens.SECUNDARIA if pagamento else tokens.TEXTO,
                700,
            ), 0, Qt.AlignTop)
            self._layout.addLayout(linha)

        self._layout.addStretch()

        # ---- ações
        if not cliente.get("ativo", True):
            bt_reativar = BotaoPrimario("Reativar cliente", icone_nome="check")
            bt_reativar.clicked.connect(lambda: self.reativar.emit(cliente))
            self._acoes.addWidget(bt_reativar)
        elif saldo > 0.009:
            acoes = QHBoxLayout()
            acoes.setSpacing(8)
            bt_receber = BotaoPrimario("Receber", icone_nome="wallet")
            bt_receber.clicked.connect(lambda: self.receber.emit(cliente))
            acoes.addWidget(bt_receber, stretch=1)
            if cliente.get("telefone"):
                bt_cobrar = BotaoSecundario("Cobrar", icone_nome="message-circle")
                bt_cobrar.setToolTip("Enviar mensagem de cobrança pelo WhatsApp")
                bt_cobrar.clicked.connect(lambda: self.cobrar.emit(cliente))
                acoes.addWidget(bt_cobrar, stretch=1)
            self._acoes.addLayout(acoes)

        bt_ficha = BotaoSecundario("Abrir ficha completa", icone_nome="user")
        bt_ficha.clicked.connect(lambda: self.abrir_ficha.emit(cliente))
        self._acoes.addWidget(bt_ficha)


class Clientes(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.clientes = []
        self._clientes_filtrados = []
        self.vendas_por_cliente = {}
        self.agregados_por_cliente = {}
        self.movimentos_por_cliente = {}
        self._selecionado_id = None
        self._linhas = {}
        self.filtro_status = "TODOS"
        self._carregando = False
        self.ordenacao = "MOVIMENTO_RECENTE"
        self.prazo_inadimplencia = cliente_analise.PRAZO_INADIMPLENCIA_PADRAO

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(12)

        self.bt_voltar = QPushButton()
        self.bt_voltar.setFixedSize(36, 36)
        self.bt_voltar.setCursor(Qt.PointingHandCursor)
        self.bt_voltar.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
        self.bt_voltar.setToolTip("Voltar")
        self.bt_voltar.setAccessibleName("Voltar")
        self.bt_voltar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        icone_titulo = QLabel()
        icone_titulo.setFixedSize(36, 36)
        icone_titulo.setAlignment(Qt.AlignCenter)
        icone_titulo.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; border-radius:{tokens.RADIUS_SM}px;
        """)
        icone_titulo.setPixmap(icone_pixmap("users", cor=tokens.PRIMARIA, tamanho=18))

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Clientes")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)

        subtitulo = QLabel(
            "Gerencie seus clientes, acompanhe o fiado e mantenha um "
            "bom relacionamento."
        )
        subtitulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XS}px;
            color:{tokens.TEXTO_TERCIARIO};
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        self.bt_exportar = BotaoSecundario("Exportar CSV", icone_nome="download")
        self.bt_exportar.clicked.connect(self.exportar_csv)

        self.bt_novo = BotaoPrimario("Novo Cliente", icone_nome="plus")
        self.bt_novo.clicked.connect(self.novo_cliente)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addWidget(icone_titulo)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(self.bt_exportar)
        cabecalho.addWidget(self.bt_novo)

        layout.addLayout(cabecalho)

        # ======================
        # CARDS DE RESUMO
        # ======================

        resumo_layout = QGridLayout()
        resumo_layout.setSpacing(14)

        # 4 números que respondem "quanto tenho na rua e quem preciso
        # cobrar" -- as contagens de Ativos/Sem Movimento/Novos que antes
        # tinham card próprio agora aparecem no próprio botão de filtro
        self.card_a_receber = CardKPI(
            "Fiado em aberto", "credit-card", tokens.PRIMARIA, destaque=True
        )
        self.card_recebido_fiado = CardKPI("Recebido de fiado", "wallet", tokens.SECUNDARIA)
        self.card_devendo = CardKPI("Clientes devendo", "users", tokens.PRIMARIA)
        self.card_inadimplentes = CardKPI("Inadimplentes", "alert-triangle", tokens.ERRO)

        for coluna, card in enumerate((
            self.card_a_receber,
            self.card_recebido_fiado,
            self.card_devendo,
            self.card_inadimplentes,
        )):
            resumo_layout.addWidget(card, 0, coluna)
            resumo_layout.setColumnStretch(coluna, 1)

        # Vendedor ve o saldo de cada cliente, nao o total da loja
        if api.usuario_tem_permissao("financeiro.ver"):
            layout.addLayout(resumo_layout)
        else:
            for coluna in range(resumo_layout.count()):
                resumo_layout.itemAt(coluna).widget().hide()

        # ======================
        # BUSCA + FILTRO
        # ======================

        # linha 1: busca + prazo/ordenação/loja; linha 2: filtros de
        # status + contagem. (Antes os 6 filtros dividiam a linha com a
        # busca e espremiam o campo até cortar o texto de exemplo.)
        barra = QHBoxLayout()
        barra.setSpacing(10)

        self.pesquisa = CampoTexto("Buscar por nome, telefone ou CPF/CNPJ...")
        self.pesquisa.setMinimumWidth(260)
        self.pesquisa.textChanged.connect(self.filtrar_clientes)

        barra.addWidget(self.pesquisa, stretch=1)

        def _legenda(texto):
            lbl = QLabel(texto)
            lbl.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            """)
            return lbl

        estilo_combo = f"""
            QComboBox {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                padding:0 12px; background:{tokens.CARD}; color:{tokens.TEXTO};
            }}
        """

        self.combo_prazo = QComboBox()
        for dias in cliente_analise.PRAZOS_INADIMPLENCIA:
            self.combo_prazo.addItem(f"Atraso: {dias} dias", dias)
        self.combo_prazo.setCurrentIndex(
            cliente_analise.PRAZOS_INADIMPLENCIA.index(
                cliente_analise.PRAZO_INADIMPLENCIA_PADRAO
            )
        )
        self.combo_prazo.setToolTip("Prazo de inadimplência")
        self.combo_prazo.setMinimumHeight(40)
        self.combo_prazo.setCursor(Qt.PointingHandCursor)
        self.combo_prazo.setStyleSheet(estilo_combo)
        self.combo_prazo.currentIndexChanged.connect(self.alterar_prazo_inadimplencia)

        self.combo_ordenacao = QComboBox()
        for rotulo, chave in ORDENACOES:
            self.combo_ordenacao.addItem(rotulo, chave)
        self.combo_ordenacao.setToolTip("Ordenar por")
        self.combo_ordenacao.setMinimumHeight(40)
        self.combo_ordenacao.setMinimumWidth(250)
        self.combo_ordenacao.setCursor(Qt.PointingHandCursor)
        self.combo_ordenacao.setStyleSheet(estilo_combo)
        self.combo_ordenacao.currentIndexChanged.connect(self.alterar_ordenacao)

        self.combo_loja_filtro = QComboBox()
        self.combo_loja_filtro.setMinimumHeight(40)
        self.combo_loja_filtro.setCursor(Qt.PointingHandCursor)
        self.combo_loja_filtro.setStyleSheet(estilo_combo)
        self._carregar_combo_lojas()
        self.combo_loja_filtro.currentIndexChanged.connect(self.carregar)

        barra.addWidget(self.combo_prazo)
        barra.addWidget(_legenda("Ordenar:"))
        barra.addWidget(self.combo_ordenacao)
        barra.addWidget(self.combo_loja_filtro)

        layout.addLayout(barra)

        barra_ordenacao = QHBoxLayout()
        barra_ordenacao.setSpacing(8)

        self.botoes_status = {}

        for rotulo, chave in FILTROS:

            bt = QPushButton(rotulo)
            bt.setProperty("rotulo", rotulo)
            bt.setCheckable(True)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setMinimumHeight(36)
            bt.setIcon(icone(_ICONES_FILTRO.get(chave, "users"), cor=tokens.TEXTO_SECUNDARIO, tamanho=15))
            bt.clicked.connect(
                lambda checked, c=chave: self.selecionar_status(c)
            )

            self.botoes_status[chave] = bt
            barra_ordenacao.addWidget(bt)

        barra_ordenacao.addStretch()

        self.lbl_contagem = QLabel("")
        self.lbl_contagem.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        barra_ordenacao.addWidget(self.lbl_contagem)

        # 8 filtros com contagem de 3 digitos passam de 1600px e a linha
        # nao quebra: sem rolagem ela empurrava a janela pra fora da tela
        faixa_filtros = QWidget()
        faixa_filtros.setStyleSheet("background:transparent;")
        barra_ordenacao.setContentsMargins(0, 0, 0, 0)
        faixa_filtros.setLayout(barra_ordenacao)
        rolagem_filtros = QScrollArea()
        rolagem_filtros.setWidget(faixa_filtros)
        rolagem_filtros.setWidgetResizable(True)
        rolagem_filtros.setFrameShape(QFrame.NoFrame)
        rolagem_filtros.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        rolagem_filtros.setStyleSheet("QScrollArea { border:none; background:transparent; }")
        rolagem_filtros.setFixedHeight(
            faixa_filtros.sizeHint().height()
            + rolagem_filtros.horizontalScrollBar().sizeHint().height()
        )
        layout.addWidget(rolagem_filtros)

        # ======================
        # GRID DE CLIENTES
        # ======================

        # lista (esquerda) + resumo do cliente selecionado (direita)
        self.area_lista = QWidget()
        self.area_lista.setStyleSheet("background:transparent;")
        corpo = QHBoxLayout(self.area_lista)
        corpo.setContentsMargins(0, 0, 0, 0)
        corpo.setSpacing(16)

        self.card_lista = Card()
        lista_layout = QVBoxLayout(self.card_lista)
        lista_layout.setContentsMargins(0, 6, 0, 6)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
        )

        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background:transparent;")
        # grid de 1 coluna (e não QVBoxLayout) só pra continuar
        # compatível com cartoes_esqueleto() no carregamento
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(0)
        self.grid_layout.setAlignment(Qt.AlignTop)

        self.scroll.setWidget(self.grid_widget)
        lista_layout.addWidget(self.scroll)

        self.painel = PainelCliente()
        self.painel.abrir_ficha.connect(self.ver_ficha)
        self.painel.receber.connect(self.receber_pagamento)
        self.painel.cobrar.connect(self.cobrar_whatsapp)
        self.painel.reativar.connect(self.reativar_cliente)

        corpo.addWidget(self.card_lista, stretch=1)
        corpo.addWidget(self.painel)

        layout.addWidget(self.area_lista, stretch=1)

        self.lbl_vazio = QLabel(
            "Nenhum cliente cadastrado ainda.\n"
            "Clique em \"Novo Cliente\" pra começar o caderninho."
        )
        self.lbl_vazio.setAlignment(Qt.AlignCenter)
        self.lbl_vazio.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_BASE}px;
        """)
        self.lbl_vazio.setVisible(False)

        layout.addWidget(self.lbl_vazio)

        self.painel_erro = PainelErro()
        self.painel_erro.tentar_novamente.connect(self.carregar)
        layout.addWidget(self.painel_erro)

        # ==========================================
        # ATALHOS DE TECLADO
        # ==========================================

        QShortcut(QKeySequence("F5"), self, self.carregar)
        QShortcut(QKeySequence("Ctrl+N"), self, self.novo_cliente)

        self.selecionar_status("TODOS")

        self.carregar()

    # ==========================================
    # CARREGAR CLIENTES
    # ==========================================

    def _carregar_combo_lojas(self):

        self.combo_loja_filtro.blockSignals(True)
        self.combo_loja_filtro.clear()
        self.combo_loja_filtro.addItem("Todas as lojas", None)
        self.combo_loja_filtro.blockSignals(False)

        rodar_em_thread(
            self,
            listar_lojas,
            ao_sucesso=self._ao_carregar_combo_lojas_sucesso,
        )

    def _ao_carregar_combo_lojas_sucesso(self, lojas):

        self.combo_loja_filtro.blockSignals(True)

        for loja in lojas:
            self.combo_loja_filtro.addItem(loja["nome"], loja["id"])

        self.combo_loja_filtro.blockSignals(False)

    def carregar(self):

        # trava contra carga dupla sobreposta (ver mesmo comentario em
        # telas/produtos.py::carregar) -- aqui tambem dispara pelo
        # combo de loja mudando enquanto uma carga anterior ainda nao
        # terminou
        if self._carregando:
            return
        self._carregando = True

        self.painel_erro.hide()
        self.lbl_vazio.setVisible(False)
        self.area_lista.setVisible(True)
        self._definir_controles_carregando(True)

        self._linhas = {}
        cartoes_esqueleto(self.grid_layout, n=7, colunas=1, altura=58)
        self.lbl_contagem.setText("Carregando...")

        loja_id = self.combo_loja_filtro.currentData()

        rodar_em_thread(
            self,
            _buscar_dados_clientes,
            loja_id,
            ao_sucesso=self._ao_carregar_sucesso,
            ao_erro=self._ao_carregar_erro,
            ao_finalizar=self._ao_carregar_finalizado,
        )

    def _definir_controles_carregando(self, carregando: bool):
        # bt_novo fica de fora de proposito, mesmo motivo do Produtos:
        # cadastrar cliente novo nao depende da listagem ja ter
        # terminado de carregar
        for widget in (self.bt_exportar, self.combo_ordenacao, self.combo_loja_filtro):
            widget.setEnabled(not carregando)
        for botao in self.botoes_status.values():
            botao.setEnabled(not carregando)

    def _ao_carregar_sucesso(self, dados):
        # a rede respondeu certinho, mas atualizar_cards_resumo/
        # filtrar_clientes ainda podem estourar por um dado inesperado
        # -- sem isso, uma excecao aqui deixava o skeleton preso na
        # tela pra sempre (o "finalizado" ja tinha rodado e reabilitado
        # os controles, mas nada trocava o skeleton por conteudo real
        # nem avisava o usuario que algo deu errado)
        try:
            (
                self.clientes,
                self.agregados_por_cliente,
                self.vendas_por_cliente,
                self.recebido_fiado_total,
                self.movimentos_por_cliente,
            ) = dados

            self.atualizar_cards_resumo()
            self.filtrar_clientes()
        except Exception as erro:
            self._ao_carregar_erro(erro)

    def _ao_carregar_erro(self, erro):
        self.grid_layout_limpar()
        self.area_lista.setVisible(False)
        self.lbl_vazio.setVisible(False)
        self.painel_erro.definir_mensagem(
            f"Não foi possível carregar os clientes.\n{erro}"
        )
        self.painel_erro.show()
        self.lbl_contagem.setText("")

    def _ao_carregar_finalizado(self):
        self._carregando = False
        self._definir_controles_carregando(False)

    def grid_layout_limpar(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    # ==========================================
    # CARDS DE RESUMO
    # ==========================================

    def atualizar_cards_resumo(self):

        # negativados ficam fora de tudo (contagens e a receber): a divida
        # deles e' dinheiro perdido, so' aparece na aba deles
        negativados = [c for c in self.clientes if c.get("negativado")]
        normais = [c for c in self.clientes if not c.get("negativado")]
        perdido = sum(
            float(self.agregados_por_cliente.get(c["id"], {}).get("perdido", 0) or 0)
            for c in negativados
        )

        total = len(normais)
        contagem = {chave: 0 for _, chave in FILTROS}
        contagem["TODOS"] = total
        contagem["NEGATIVADOS"] = len(negativados)

        devendo = 0
        valor_inadimplente = 0.0

        for cliente in normais:

            agr = self.agregados_por_cliente.get(cliente["id"])

            if not agr:
                continue

            if cliente_analise.eh_ativo(agr):
                contagem["ATIVOS"] += 1
            if cliente_analise.eh_sem_movimento(agr, self.prazo_inadimplencia):
                contagem["SEM_MOVIMENTO"] += 1
            if cliente_analise.eh_inadimplente(agr, self.prazo_inadimplencia):
                contagem["INADIMPLENTES"] += 1
                valor_inadimplente += agr["saldo_devedor"]
            if cliente_analise.eh_em_dia(agr):
                contagem["EM_DIA"] += 1
            else:
                devendo += 1
            if cliente_analise.eh_novo(agr):
                contagem["NOVOS"] += 1
            if cliente_analise.eh_bom_pagador(agr, self.prazo_inadimplencia):
                contagem["BONS_PAGADORES"] += 1

        total_a_receber = sum(
            float(c.get("saldo_fiado", 0) or 0) for c in normais
        )

        self.card_a_receber.definir_valor(formatar_moeda(total_a_receber))
        self.card_a_receber.definir_legenda(
            f"{devendo} cliente{'s' if devendo != 1 else ''} com saldo"
            + (f" · {formatar_moeda(perdido)} perdido (negativados)" if perdido else "")
        )
        self.card_recebido_fiado.definir_valor(
            formatar_moeda(self.recebido_fiado_total)
        )
        self.card_recebido_fiado.definir_legenda("pagamentos de fiado recebidos nesta loja")
        self.card_devendo.definir_valor(str(devendo))
        self.card_devendo.definir_legenda(f"de {total} cadastros")
        self.card_inadimplentes.definir_valor(str(contagem["INADIMPLENTES"]))
        self.card_inadimplentes.definir_legenda(
            f"{formatar_moeda(valor_inadimplente)} parados há mais de "
            f"{self.prazo_inadimplencia} dias"
        )

        for chave, botao in self.botoes_status.items():
            botao.setText(f"{botao.property('rotulo')}  {contagem.get(chave, 0)}")

    # ==========================================
    # FILTRO DE STATUS
    # ==========================================

    def selecionar_status(self, chave):

        self.filtro_status = chave

        for k, botao in self.botoes_status.items():

            selecionado = k == chave

            botao.setChecked(selecionado)
            botao.setIcon(icone(
                _ICONES_FILTRO.get(k, "users"),
                cor=tokens.PRIMARIA if selecionado else tokens.TEXTO_SECUNDARIO,
                tamanho=14,
            ))

            # pílula clara (e não azul cheio) -- o azul cheio fica
            # reservado pro botão de ação principal da tela
            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {tokens.PRIMARIA_CLARA if selecionado else tokens.CARD};
                    color: {tokens.PRIMARIA if selecionado else tokens.TEXTO_SECUNDARIO};
                    border-radius: 18px;
                    border: 1px solid {tokens.PRIMARIA_CLARA if selecionado else tokens.BORDA};
                    font-weight: {700 if selecionado else 600};
                    font-size: {tokens.TAMANHO_SM}px;
                    padding: 0 14px;
                }}
                QPushButton:hover {{
                    background: {tokens.PRIMARIA_CLARA if selecionado else tokens.FUNDO};
                }}
            """)

        self.filtrar_clientes()

    # ==========================================
    # PRAZO DE INADIMPLÊNCIA
    # ==========================================

    def alterar_prazo_inadimplencia(self, _indice):

        self.prazo_inadimplencia = self.combo_prazo.currentData()

        self.atualizar_cards_resumo()
        self.filtrar_clientes()

    # ==========================================
    # ORDENAÇÃO
    # ==========================================

    def alterar_ordenacao(self, _indice):

        self.ordenacao = self.combo_ordenacao.currentData()

        self.filtrar_clientes()

    # ==========================================
    # FILTRAR CLIENTES
    # ==========================================

    def filtrar_clientes(self):

        texto = self.pesquisa.text().lower().strip()

        negativados = self.filtro_status == "NEGATIVADOS"
        clientes = [c for c in self.clientes if bool(c.get("negativado")) == negativados]

        def agr(c):
            return self.agregados_por_cliente.get(c["id"], {})

        if self.filtro_status == "ATIVOS":
            clientes = [
                c for c in clientes if cliente_analise.eh_ativo(agr(c))
            ]
        elif self.filtro_status == "SEM_MOVIMENTO":
            clientes = [
                c for c in clientes
                if cliente_analise.eh_sem_movimento(
                    agr(c), self.prazo_inadimplencia
                )
            ]
        elif self.filtro_status == "INADIMPLENTES":
            clientes = [
                c for c in clientes
                if cliente_analise.eh_inadimplente(
                    agr(c), self.prazo_inadimplencia
                )
            ]
        elif self.filtro_status == "EM_DIA":
            clientes = [
                c for c in clientes if cliente_analise.eh_em_dia(agr(c))
            ]
        elif self.filtro_status == "NOVOS":
            clientes = [
                c for c in clientes if cliente_analise.eh_novo(agr(c))
            ]
        elif self.filtro_status == "BONS_PAGADORES":
            clientes = [
                c for c in clientes
                if cliente_analise.eh_bom_pagador(
                    agr(c), self.prazo_inadimplencia
                )
            ]

        if texto != "":

            filtrados = []

            for cliente in clientes:

                nome = str(cliente.get("nome") or "").lower()
                whatsapp = str(cliente.get("telefone") or "").lower()
                cpf = str(cliente.get("cpf_cnpj") or "").lower()

                if (
                    texto in nome
                    or texto in whatsapp
                    or texto in cpf
                ):
                    filtrados.append(cliente)

            clientes = filtrados

        clientes = self._ordenar(clientes)

        # guardado pra exportar exatamente o que esta na tela (filtro
        # + busca + ordenacao aplicados), nao a lista inteira sem filtro
        self._clientes_filtrados = clientes

        self.lbl_contagem.setText(
            "1 cliente encontrado" if len(clientes) == 1
            else f"{len(clientes)} clientes encontrados"
        )

        self.preencher_grid(clientes)

    def _ordenar(self, clientes):

        def agr(c):
            return self.agregados_por_cliente.get(c["id"], {})

        def nome(c):
            return (c.get("nome") or "").lower()

        # datas/numeros ausentes sempre vao pro final da lista,
        # independente da direcao da ordenacao
        def chave_data(campo, reverso):
            def _chave(c):
                valor = agr(c).get(campo)
                ausente = valor is None
                if reverso:
                    return (ausente, -valor.timestamp() if valor else 0)
                return (ausente, valor.timestamp() if valor else 0)
            return _chave

        if self.ordenacao == "MOVIMENTO_RECENTE":
            return sorted(
                clientes, key=chave_data("ultima_movimentacao", True)
            )
        if self.ordenacao == "MOVIMENTO_ANTIGO":
            return sorted(
                clientes, key=chave_data("ultima_movimentacao", False)
            )
        if self.ordenacao == "ULTIMA_COMPRA":
            return sorted(clientes, key=chave_data("ultima_compra", True))
        if self.ordenacao == "MAIOR_COMPRA":
            return sorted(
                clientes,
                key=lambda c: agr(c).get("maior_compra", 0),
                reverse=True,
            )
        if self.ordenacao == "MAIOR_SALDO":
            return sorted(
                clientes,
                key=lambda c: agr(c).get("saldo_devedor", 0),
                reverse=True,
            )
        if self.ordenacao == "NOME_ZA":
            return sorted(clientes, key=nome, reverse=True)
        if self.ordenacao == "CADASTRO_ANTIGO":
            return sorted(clientes, key=chave_data("criado_em", False))
        if self.ordenacao == "CADASTRO_NOVO":
            return sorted(clientes, key=chave_data("criado_em", True))

        # NOME_AZ e qualquer chave desconhecida caem aqui
        return sorted(clientes, key=nome)

    # ==========================================
    # PREENCHER GRID
    # ==========================================

    def preencher_grid(self, clientes):

        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()

        self._linhas = {}

        for indice, cliente in enumerate(clientes):

            linha = ClienteLinha(
                cliente,
                self.agregados_por_cliente.get(cliente["id"]),
                self.prazo_inadimplencia,
            )
            linha.selecionado.connect(self.selecionar_cliente)
            linha.abrir.connect(self.ver_ficha)

            self._linhas[cliente["id"]] = linha
            self.grid_layout.addWidget(linha, indice, 0)

        self.area_lista.setVisible(len(clientes) > 0)
        self.lbl_vazio.setVisible(len(clientes) == 0)

        # mantém o mesmo cliente selecionado entre recargas/filtros; se
        # ele saiu da lista, cai pro primeiro da lista atual
        ids = [c["id"] for c in clientes]
        if self._selecionado_id not in ids:
            self._selecionado_id = ids[0] if ids else None
        self._atualizar_selecao()

    def selecionar_cliente(self, cliente):

        if cliente["id"] == self._selecionado_id:
            return
        self._selecionado_id = cliente["id"]
        self._atualizar_selecao()

    def _atualizar_selecao(self):

        for cid, linha in self._linhas.items():
            linha.definir_selecionado(cid == self._selecionado_id)

        cliente = next(
            (c for c in self.clientes if c["id"] == self._selecionado_id), None
        )
        self.painel.mostrar(
            cliente,
            self.agregados_por_cliente.get(self._selecionado_id),
            self.movimentos_por_cliente.get(self._selecionado_id, []),
            self.prazo_inadimplencia,
        )

    # ==========================================
    # AÇÕES
    # ==========================================

    def novo_cliente(self):

        tela = CadastroClienteDialog(parent=self)

        if tela.exec() != QDialog.Accepted:
            return

        self.carregar()

    def ver_ficha(self, cliente):

        self._abrir_ficha(cliente)

    def receber_pagamento(self, cliente):
        # reaproveita o fluxo de pagamento da ficha (checagem de saldo,
        # diálogo, recibo) em vez de duplicar aqui -- a ficha abre e já
        # chama o "Registrar pagamento" assim que aparece na tela
        self._abrir_ficha(cliente, acao="registrar_pagamento")

    def cobrar_whatsapp(self, cliente):
        self._abrir_ficha(cliente, acao="enviar_cobranca_whatsapp")

    def _abrir_ficha(self, cliente, acao=None):

        tela = FichaClienteDialog(cliente, parent=self)

        if acao:
            QTimer.singleShot(0, getattr(tela, acao))

        tela.exec()

        self.carregar()

    def reativar_cliente(self, cliente):

        resposta = QMessageBox.question(
            self,
            "Reativar Cliente",
            f"Reativar \"{cliente.get('nome')}\"?",
        )

        if resposta != QMessageBox.Yes:
            return

        response = reativar_cliente(cliente["id"])

        if response.status_code != 200:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
            return

        self.carregar()

    def exportar_csv(self):

        # exporta exatamente o que esta na tela agora (filtro + busca +
        # ordenacao aplicados), nao a base de clientes inteira
        if not self._clientes_filtrados:
            QMessageBox.information(
                self,
                "Nada para exportar",
                "Não há clientes na lista atual pra exportar.",
            )
            return

        caminho, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Clientes (CSV)",
            "clientes.csv",
            "Arquivo CSV (*.csv)",
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".csv"):
            caminho += ".csv"

        try:
            with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:

                escritor = csv.writer(arquivo, delimiter=";")
                escritor.writerow([
                    "Nome", "Telefone", "CPF/CNPJ", "E-mail",
                    "Saldo Devedor", "Última Movimentação", "Status",
                ])

                for cliente in self._clientes_filtrados:

                    agr = self.agregados_por_cliente.get(cliente["id"], {})

                    ultima_mov = agr.get("ultima_movimentacao")
                    texto_ultima_mov = (
                        ultima_mov.strftime("%d/%m/%Y") if ultima_mov else ""
                    )

                    escritor.writerow([
                        cliente.get("nome", ""),
                        cliente.get("telefone", "") or "",
                        cliente.get("cpf_cnpj", "") or "",
                        cliente.get("email", "") or "",
                        f"{float(cliente.get('saldo_fiado', 0) or 0):.2f}",
                        texto_ultima_mov,
                        "Ativo" if cliente.get("ativo", True) else "Inativo",
                    ])

            QMessageBox.information(
                self, "Sucesso", "Lista de clientes exportada com sucesso."
            )

        except OSError as erro:
            QMessageBox.critical(self, "Erro", str(erro))
