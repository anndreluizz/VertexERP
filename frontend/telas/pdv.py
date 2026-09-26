import uuid
from datetime import datetime, timedelta

from telas.pagamento import PagamentoWindow
from telas.buscar_produto import BuscarProdutoDialog
from telas.venda_concluida import VendaConcluidaDialog
from telas.cadastro_produto import CadastroProdutoWindow
from telas.selecionar_cliente import SelecionarClienteDialog
from services.venda_service import (
    finalizar_venda as enviar_venda,
    suspender_venda as enviar_suspensao,
    listar_vendas_suspensas,
    excluir_venda_suspensa,
)
from services.worker import rodar_em_thread
from services.produto_service import (
    listar_produtos,
    cadastrar_produto,
    obter_foto_produto,
)
from services.pdv_service import buscar_produto
from services.caixa_service import caixa_aberto
from services.relatorio_service import relatorio_vendas
from services.api import configuracoes, me
from services import preferencias_service, comprovante_service
from utils.documento_html import (
    ESTILO_BODY,
    bloco_total,
    cabecalho_html,
    cabecalho_tabela,
    linha_zebra,
    rodape_nao_fiscal,
)

ATALHOS_PADRAO = {"busca": "F1", "cadastro_rapido": "F4", "cancelar": "Esc"}

from PySide6.QtCore import Qt, QTimer, Signal, QSize, QEvent
from PySide6.QtGui import (
    QShortcut,
    QKeySequence,
    QFont,
    QTextDocument,
    QCursor,
    QPixmap,
)
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QFileDialog,
)

from design import tokens
from design.animations import fade_in
from design.icons import icone, icone_pixmap
from design.widgets import (
    Badge,
    BotaoPerigo,
    BotaoPrimario,
    BotaoSecundario,
    BotaoSucesso,
    CampoTexto,
)
from utils.formatacao import formatar_moeda

LARGURA_PAINEL_RESUMO = 340

_CORES_MONOGRAMA = [
    "#2563EB", "#16A34A", "#D97706", "#DB2777", "#7C3AED", "#0891B2",
]


def _parse_data(texto):
    try:
        return datetime.fromisoformat(texto)
    except (ValueError, TypeError):
        return None


def _separar_multiplicador(texto):
    """"3*789..." -> (3, "789..."); sem "*" -> (1, texto). So' aceita
    inteiro de 1 a 9999 antes do "*" -- qualquer outra coisa e' tratada
    como parte do codigo/nome."""

    antes, separador, depois = texto.partition("*")

    if separador and antes.strip().isdigit() and 0 < int(antes) < 10000:
        return int(antes), depois.strip()

    return 1, texto


def _baixar_foto_com_id(produto_id):
    """Roda na worker thread -- o id viaja junto com os bytes (nao da'
    pra usar closure como callback, ver services/worker.py)."""
    return produto_id, obter_foto_produto(produto_id)


def _parse_valor(texto):
    try:
        return max(0.0, float((texto or "").strip().replace(",", ".") or 0))
    except ValueError:
        return 0.0


class VendasSuspensasDialog(QDialog):
    """Lista as vendas suspensas (persistidas no backend como
    Venda.status=ABERTA -- sobrevivem a fechar o app e aparecem pra
    qualquer terminal da mesma loja, ver VendaService.suspender/
    listar_suspensas). Permite retomar ou excluir uma venda suspensa.

    `vendas_suspensas` vem de GET /vendas/suspensas -- cada item ja
    traz nome/codigo/estoque atual do produto embutido (ver
    VendaSuspensaResponse no backend), pra retomar nao precisar de
    uma chamada extra por produto."""

    def __init__(self, vendas_suspensas, parent=None):

        super().__init__(parent)

        self.indice_selecionado = None
        self.acao = None

        self.setWindowTitle("Vendas Suspensas")
        self.resize(480, 420)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        titulo = QLabel("Vendas Suspensas")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)
        layout.addWidget(titulo)

        self.lista = QTableWidget()
        self.lista.setColumnCount(1)
        self.lista.horizontalHeader().setVisible(False)
        self.lista.verticalHeader().setVisible(False)
        self.lista.setSelectionBehavior(QTableWidget.SelectRows)
        self.lista.setSelectionMode(QTableWidget.SingleSelection)
        self.lista.setEditTriggers(QTableWidget.NoEditTriggers)
        self.lista.horizontalHeader().setStretchLastSection(True)
        self.lista.setStyleSheet(f"""
            QTableWidget {{
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                background:{tokens.CARD};
            }}
        """)

        self.lista.setRowCount(len(vendas_suspensas))

        for linha, venda in enumerate(vendas_suspensas):

            total = sum(
                float(item["valor_unitario"]) * item["quantidade"]
                for item in venda["itens"]
            )
            hora_texto = _parse_data(venda["data"]).strftime("%H:%M")

            rotulo = f"Venda #{venda['id']}"
            if venda.get("cliente_nome"):
                rotulo += f" — {venda['cliente_nome']}"

            texto = (
                f"{rotulo}   ·   {len(venda['itens'])} item(ns)   ·   "
                f"{formatar_moeda(total)}   ·   {hora_texto}"
            )

            self.lista.setItem(linha, 0, QTableWidgetItem(texto))

        self.lista.verticalHeader().setDefaultSectionSize(40)

        if self.lista.rowCount() > 0:
            self.lista.selectRow(0)

        layout.addWidget(self.lista, stretch=1)

        rodape = QHBoxLayout()
        rodape.setSpacing(10)

        bt_excluir = BotaoPerigo("Excluir")
        bt_excluir.clicked.connect(self._excluir)

        bt_retomar = BotaoPrimario("Retomar")
        bt_retomar.clicked.connect(self._retomar)

        rodape.addWidget(bt_excluir)
        rodape.addStretch()
        rodape.addWidget(bt_retomar)

        layout.addLayout(rodape)

    def _linha_atual(self):
        linhas = self.lista.selectionModel().selectedRows()
        return linhas[0].row() if linhas else -1

    def _retomar(self):
        linha = self._linha_atual()
        if linha < 0:
            return
        self.indice_selecionado = linha
        self.acao = "retomar"
        self.accept()

    def _excluir(self):
        linha = self._linha_atual()
        if linha < 0:
            return
        self.indice_selecionado = linha
        self.acao = "excluir"
        self.accept()


class PDV(QWidget):

    voltar = Signal()

    def __init__(self):
        super().__init__()

        self.itens = []
        # chave de idempotencia do carrinho atual (ver finalizar_venda)
        self._chave_venda = None
        self.cliente_id = None
        self.cliente_nome = None
        self.desconto_valor = 0.0
        self.acrescimo_valor = 0.0
        self._finalizando_venda = False
        self._suspendendo_venda = False
        # destaque "ultimo item lido" -- id do produto, nao indice da
        # linha, pra continuar certo quando outra linha e' removida
        self._id_ultimo_item = None
        self._fotos_cache = {}

        self._usuario_id = (me() or {}).get("id")
        self.atalhos = self._carregar_atalhos()

        self.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Cabeçalho — largura plena, acima das duas colunas.
        layout.addLayout(self._construir_cabecalho())

        # ======================
        # CORPO: carrinho fica numa área que rola se a janela for
        # baixa demais (mesma solução já usada antes pra não estourar
        # em notebooks/1366x768) — o painel de resumo financeiro +
        # botão Pagar fica de fora da rolagem, sempre visível, à
        # direita.
        # ======================

        corpo = QHBoxLayout()
        corpo.setContentsMargins(24, 4, 24, 20)
        corpo.setSpacing(20)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background:transparent; border:none; }")

        coluna_esquerda = QWidget()
        coluna_esquerda.setStyleSheet("background:transparent;")

        layout_esquerda = QVBoxLayout(coluna_esquerda)
        layout_esquerda.setContentsMargins(0, 0, 4, 0)
        layout_esquerda.setSpacing(12)

        # layout de caixa de loja: ultimo item em destaque, campo de
        # codigo, e a lista em formato de cupom; cliente/totais ficam
        # no painel da direita, com o TOTAL grande
        layout_esquerda.addWidget(self._construir_ultimo_item())
        layout_esquerda.addWidget(self._construir_campo_codigo())
        layout_esquerda.addWidget(self.lbl_status_busca)
        layout_esquerda.addWidget(self._construir_mais_vendidos())
        layout_esquerda.addWidget(self._construir_cartao_tabela(), stretch=1)

        self.tabela.setMinimumHeight(160)

        scroll.setWidget(coluna_esquerda)
        corpo.addWidget(scroll, stretch=1)

        painel_resumo = QWidget()
        painel_resumo.setFixedWidth(LARGURA_PAINEL_RESUMO)
        painel_resumo.setStyleSheet("background:transparent;")

        layout_resumo = QVBoxLayout(painel_resumo)
        layout_resumo.setContentsMargins(0, 0, 0, 0)
        layout_resumo.setSpacing(12)

        # stretch=1 pro cartão de resumo acompanhar a altura do
        # carrinho ao lado, em vez de ficar pequeno com um vão cinza
        # vazio embaixo — o conteúdo continua compacto e ancorado no
        # topo do card (ver stretch interno em _construir_cartao_resumo).
        layout_resumo.addWidget(self._construir_cartao_resumo(), stretch=1)
        layout_resumo.addWidget(self._construir_botao_pagar())

        corpo.addWidget(painel_resumo)

        layout.addLayout(corpo, stretch=1)

        layout.addWidget(self._construir_barra_atalhos())

        # ======================
        # ATALHOS DE TECLADO
        # ======================

        contexto = Qt.WidgetWithChildrenShortcut

        self.atalho_f1 = QShortcut(QKeySequence(self.atalhos["busca"]), self)
        self.atalho_f1.setContext(contexto)
        self.atalho_f1.activated.connect(self.abrir_busca)

        self.atalho_f4 = QShortcut(QKeySequence(self.atalhos["cadastro_rapido"]), self)
        self.atalho_f4.setContext(contexto)
        self.atalho_f4.activated.connect(self.abrir_novo_produto)

        self.atalho_esc = QShortcut(QKeySequence(self.atalhos["cancelar"]), self)
        self.atalho_esc.setContext(contexto)
        self.atalho_esc.activated.connect(self.cancelar_venda)

        # F2 (cliente) e F6 (desconto/acréscimo) não conflitam com
        # nenhum atalho existente e já têm uma ação óbvia associada —
        # F3 (pagar) continua tratado globalmente por PrincipalWindow.
        self.atalho_f2 = QShortcut(QKeySequence("F2"), self)
        self.atalho_f2.setContext(contexto)
        self.atalho_f2.activated.connect(self.abrir_selecionar_cliente)

        self.atalho_f6 = QShortcut(QKeySequence("F6"), self)
        self.atalho_f6.setContext(contexto)
        self.atalho_f6.activated.connect(self._alternar_bloco_ajuste)

        self.atalho_f7 = QShortcut(QKeySequence("F7"), self)
        self.atalho_f7.setContext(contexto)
        self.atalho_f7.activated.connect(self._abrir_ajuste_acrescimo)

        # Del / + / - / setas agem no item selecionado do cupom, tanto
        # com o foco no campo de codigo (vazio) quanto na propria lista
        self.campo_codigo.installEventFilter(self)
        self.tabela.installEventFilter(self)

        fade_in(self, duracao=200)

    def showEvent(self, event):
        super().showEvent(event)
        self.recarregar_atalhos()
        self.campo_codigo.setFocus()
        # as duas chamadas abaixo dependem do backend (rede) -- adiadas
        # pro próximo ciclo de eventos pra tela do PDV aparecer na hora
        # em vez de travar a troca de aba esperando a resposta.
        QTimer.singleShot(0, self.atualizar_indicador_caixa)
        QTimer.singleShot(0, self.atualizar_mais_vendidos)
        QTimer.singleShot(0, self._atualizar_contagem_suspensas)

    def _carregar_atalhos(self):
        salvo = preferencias_service.carregar(self._usuario_id, "pdv_atalhos", {})
        return {**ATALHOS_PADRAO, **(salvo or {})}

    def recarregar_atalhos(self):
        """Reflete na hora qualquer remapeamento feito em Configurações
        — chamado toda vez que a tela do PDV é reaberta, já que o
        widget nunca é recriado enquanto o app está de pé."""

        self.atalhos = self._carregar_atalhos()

        self.atalho_f1.setKey(QKeySequence(self.atalhos["busca"]))
        self.atalho_f4.setKey(QKeySequence(self.atalhos["cadastro_rapido"]))
        self.atalho_esc.setKey(QKeySequence(self.atalhos["cancelar"]))

        self.bt_buscar.setText(f"Buscar ({self.atalhos['busca']})")
        self.bt_adicionar.setText(f"Novo Produto ({self.atalhos['cadastro_rapido']})")

        self.lbl_atalho_busca_tecla.setText(self.atalhos["busca"])
        self.lbl_atalho_produto_tecla.setText(self.atalhos["cadastro_rapido"])

    # ==================================================
    # CONSTRUÇÃO DA INTERFACE
    # ==================================================

    def _construir_cabecalho(self):

        cabecalho = QHBoxLayout()
        cabecalho.setContentsMargins(24, 16, 24, 12)
        cabecalho.setSpacing(10)

        self.bt_voltar = QPushButton()
        self.bt_voltar.setFixedSize(38, 38)
        self.bt_voltar.setCursor(Qt.PointingHandCursor)
        self.bt_voltar.setIcon(icone("chevron-left", cor=tokens.TEXTO_SECUNDARIO, tamanho=18))
        self.bt_voltar.setToolTip("Voltar")
        self.bt_voltar.setAccessibleName("Voltar")
        self.bt_voltar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background: {tokens.FUNDO}; }}
        """)
        self.bt_voltar.clicked.connect(self.voltar.emit)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Frente de Caixa")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_XL}px; font-weight:800;
        """)

        config = configuracoes()
        nome_loja = config.get("nome_loja") or ""

        # logo da loja no cabecalho -- mesma imagem usada nos
        # comprovantes, pra dar uma cara mais profissional pro PDV
        # (fica de frente pro cliente, no caixa). So aparece se a loja
        # tiver logo cadastrado em Configuracoes.
        self.lbl_logo_pdv = QLabel()
        self.lbl_logo_pdv.setFixedSize(40, 40)
        self.lbl_logo_pdv.setAlignment(Qt.AlignCenter)
        self.lbl_logo_pdv.setStyleSheet("background:transparent; border:none;")
        self.lbl_logo_pdv.setVisible(False)

        logo_bytes = None
        if config.get("tem_logo"):
            try:
                logo_bytes = comprovante_service.obter_logo_loja()
            except Exception:
                # rede/servidor instavel nao pode derrubar a tela do
                # PDV inteira so por causa da logo -- pior caso e' o
                # cabecalho ficar sem ela, igual quando a loja nao tem
                # logo cadastrado
                logo_bytes = None

        if logo_bytes:
            pixmap_logo = QPixmap()
            if pixmap_logo.loadFromData(logo_bytes):
                self.lbl_logo_pdv.setPixmap(
                    pixmap_logo.scaled(
                        40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                )
                self.lbl_logo_pdv.setVisible(True)

        self.lbl_loja = QLabel(nome_loja)
        self.lbl_loja.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(self.lbl_loja)

        self.badge_caixa = Badge("Caixa aberto", "sucesso")

        self.bt_retomar = self._botao_ghost_cabecalho("Vendas Suspensas")
        self.bt_retomar.setEnabled(False)
        self.bt_retomar.clicked.connect(self.abrir_vendas_suspensas)

        self.bt_suspender = self._botao_ghost_cabecalho("Suspender")
        self.bt_suspender.clicked.connect(self.suspender_venda)

        self.bt_orcamento = self._botao_ghost_cabecalho("Orçamento", icone_nome="printer")
        self.bt_orcamento.clicked.connect(self.imprimir_orcamento)

        self.bt_cancelar = BotaoPerigo("Cancelar Venda", icone_nome="x")
        self.bt_cancelar.clicked.connect(self.cancelar_venda)

        cabecalho.addWidget(self.bt_voltar)
        cabecalho.addWidget(self.lbl_logo_pdv)
        cabecalho.addLayout(col_titulo)
        cabecalho.addSpacing(4)
        cabecalho.addWidget(self.badge_caixa, alignment=Qt.AlignVCenter)
        cabecalho.addStretch()
        cabecalho.addWidget(self.bt_retomar)
        cabecalho.addWidget(self.bt_suspender)
        cabecalho.addWidget(self.bt_orcamento)
        cabecalho.addWidget(self.bt_cancelar)

        return cabecalho

    def _botao_ghost_cabecalho(self, texto, icone_nome=None):
        """Botão de ação secundária do cabeçalho sem contorno -- só
        fundo sutil no hover. As 3 ações daqui (Vendas Suspensas,
        Suspender, Orçamento) são usadas bem menos que Cancelar Venda
        e não precisam do mesmo peso visual de um botão contornado
        (pedido direto: menos linha no cabeçalho)."""

        bt = QPushButton(texto)
        bt.setCursor(Qt.PointingHandCursor)
        bt.setMinimumHeight(38)

        if icone_nome:
            bt.setIcon(icone(icone_nome, cor=tokens.TEXTO_SECUNDARIO, tamanho=15))
            bt.setIconSize(QSize(15, 15))

        bt.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none; border-radius:{tokens.RADIUS_SM}px;
                padding:0 12px; color:{tokens.TEXTO_SECUNDARIO};
                font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            }}
            QPushButton:hover:enabled {{ background:{tokens.FUNDO}; }}
            QPushButton:disabled {{
                background:{tokens.BORDA}; color:{tokens.TEXTO_TERCIARIO};
            }}
        """)

        return bt

    def _construir_barra_atalhos(self):

        barra = QFrame()
        barra.setFixedHeight(42)
        barra.setStyleSheet(f"""
            QFrame {{
                background: {tokens.FUNDO};
                border: none;
            }}
        """)
        # a barra nunca pode ditar a largura minima do PDV -- como todas
        # as telas dividem a mesma janela (QStackedWidget), uma barra
        # comprida aqui alargava o app inteiro alem da tela (1600px)
        barra.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        layout = QHBoxLayout(barra)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        self.lbl_atalho_busca_tecla, item_busca = self._item_atalho(
            self.atalhos["busca"], "Buscar"
        )
        self.lbl_atalho_produto_tecla, item_produto = self._item_atalho(
            self.atalhos["cadastro_rapido"], "Novo produto"
        )
        _, item_cliente = self._item_atalho("F2", "Cliente")
        _, item_finalizar = self._item_atalho("F3", "Finalizar")
        _, item_desconto = self._item_atalho("F6", "Desconto")
        _, item_acrescimo = self._item_atalho("F7", "Acréscimo")
        _, item_quantidade = self._item_atalho("+ −", "Quantidade")
        _, item_remover = self._item_atalho("Del", "Remover")

        for item in (
            item_busca, item_cliente, item_finalizar,
            item_produto, item_desconto, item_acrescimo,
            item_quantidade, item_remover,
        ):
            layout.addLayout(item)

        layout.addStretch()

        self.lbl_relogio_pdv = QLabel()
        self.lbl_relogio_pdv.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        layout.addWidget(self.lbl_relogio_pdv)

        self._timer_relogio_pdv = QTimer(self)
        self._timer_relogio_pdv.timeout.connect(self._atualizar_relogio_pdv)
        self._timer_relogio_pdv.start(1000)
        self._atualizar_relogio_pdv()

        return barra

    def _item_atalho(self, tecla, rotulo):

        item = QHBoxLayout()
        item.setSpacing(6)

        badge_tecla = QLabel(tecla)
        badge_tecla.setAlignment(Qt.AlignCenter)
        badge_tecla.setFixedHeight(20)
        badge_tecla.setStyleSheet(f"""
            background:{tokens.CARD}; color:{tokens.TEXTO_SECUNDARIO};
            border:none; border-radius:4px;
            font-size:{tokens.TAMANHO_XS}px; font-weight:700; padding: 0 6px;
        """)

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px;
        """)

        item.addWidget(badge_tecla)
        item.addWidget(lbl_rotulo)

        return badge_tecla, item

    def _atualizar_relogio_pdv(self):
        self.lbl_relogio_pdv.setText(datetime.now().strftime("%d/%m/%Y  ·  %H:%M"))

    def _construir_campo_codigo(self):

        container = QFrame()
        container.setFixedHeight(64)
        container.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border: 2px solid {tokens.PRIMARIA};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        layout = QHBoxLayout(container)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(12)

        self.campo_codigo = QLineEdit()
        self.campo_codigo.setPlaceholderText(
            "Código de barras, código ou nome  ·  3* antes = 3 unidades"
        )
        self.campo_codigo.setFont(QFont(tokens.FONTE_FAMILIA_PADRAO, 18))
        self.campo_codigo.setStyleSheet(f"""
            QLineEdit {{
                border: none; outline: none; background: transparent;
                color: {tokens.TEXTO}; font-size: 18px; font-weight: 600;
            }}
        """)
        # ícone desenhado dentro do próprio campo (QLineEdit.addAction)
        # em vez de um QLabel separado ao lado -- evita qualquer
        # contorno/moldura indesejada que um widget irmão poderia
        # ganhar do estilo do Qt quando o campo está focado.
        self.campo_codigo.addAction(
            icone("search", cor=tokens.PRIMARIA, tamanho=20),
            QLineEdit.LeadingPosition,
        )
        self.campo_codigo.returnPressed.connect(self.processar_codigo)
        self.campo_codigo.textChanged.connect(self._atualizar_multiplicador)
        layout.addWidget(self.campo_codigo, stretch=1)

        # "3*" digitado antes do codigo -- mostra que a proxima leitura
        # vai entrar com essa quantidade (ver processar_codigo)
        self.lbl_multiplicador = QLabel()
        self.lbl_multiplicador.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; color:{tokens.PRIMARIA};
            font-size:{tokens.TAMANHO_MD}px; font-weight:800; border:none;
            border-radius:{tokens.RADIUS_PILL}px; padding: 4px 12px;
        """)
        self.lbl_multiplicador.setVisible(False)
        layout.addWidget(self.lbl_multiplicador)

        # Buscar / Novo produto -- formas alternativas de adicionar
        # item, coladas no campo; discretas porque o caminho principal
        # e' o leitor/teclado (F1/F4)
        estilo_bt_campo = f"""
            QPushButton {{
                background:{tokens.FUNDO}; color:{tokens.TEXTO_SECUNDARIO};
                border:none; border-radius:{tokens.RADIUS_SM}px;
                font-size:{tokens.TAMANHO_SM}px; font-weight:700;
                padding: 0 12px;
            }}
            QPushButton:hover {{ background:{tokens.BORDA}; color:{tokens.TEXTO}; }}
        """

        self.bt_buscar = QPushButton(f"Buscar ({self.atalhos['busca']})")
        self.bt_buscar.setIcon(icone("search", cor=tokens.TEXTO_SECUNDARIO, tamanho=14))
        self.bt_buscar.setCursor(Qt.PointingHandCursor)
        self.bt_buscar.setFixedHeight(36)
        self.bt_buscar.setFocusPolicy(Qt.NoFocus)
        self.bt_buscar.setStyleSheet(estilo_bt_campo)
        self.bt_buscar.clicked.connect(self.abrir_busca)
        layout.addWidget(self.bt_buscar)

        self.bt_adicionar = QPushButton(
            f"Novo Produto ({self.atalhos['cadastro_rapido']})"
        )
        self.bt_adicionar.setIcon(icone("plus", cor=tokens.TEXTO_SECUNDARIO, tamanho=14))
        self.bt_adicionar.setCursor(Qt.PointingHandCursor)
        self.bt_adicionar.setFixedHeight(36)
        self.bt_adicionar.setFocusPolicy(Qt.NoFocus)
        self.bt_adicionar.setStyleSheet(estilo_bt_campo)
        self.bt_adicionar.clicked.connect(self.abrir_novo_produto)
        layout.addWidget(self.bt_adicionar)

        self.lbl_status_busca = QLabel("")
        self.lbl_status_busca.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px;
            font-weight:600; padding-left: 4px;
        """)

        return container

    def _construir_ultimo_item(self):
        """Faixa de destaque do ultimo produto lido (foto ou inicial,
        nome grande, "qtd x unitario" e o total da linha) -- o que o
        operador e o cliente olham pra confirmar que a leitura entrou
        certa, igual aos PDVs de supermercado."""

        self.cartao_ultimo = QFrame()
        self.cartao_ultimo.setObjectName("cartaoUltimoItem")
        self.cartao_ultimo.setFixedHeight(112)
        self.cartao_ultimo.setStyleSheet(f"""
            QFrame#cartaoUltimoItem {{
                background: {tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        layout = QHBoxLayout(self.cartao_ultimo)
        layout.setContentsMargins(14, 12, 22, 12)
        layout.setSpacing(16)

        self.lbl_ultimo_foto = QLabel()
        self.lbl_ultimo_foto.setFixedSize(86, 86)
        self.lbl_ultimo_foto.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_ultimo_foto)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(2)

        self.lbl_ultimo_rotulo = QLabel()
        self.lbl_ultimo_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800; letter-spacing:0.5px;
        """)

        self.lbl_ultimo_nome = QLabel()
        self.lbl_ultimo_nome.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:24px; font-weight:800;
        """)

        self.lbl_ultimo_conta = QLabel()
        self.lbl_ultimo_conta.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_MD}px; font-weight:600;
        """)

        col_texto.addStretch()
        col_texto.addWidget(self.lbl_ultimo_rotulo)
        col_texto.addWidget(self.lbl_ultimo_nome)
        col_texto.addWidget(self.lbl_ultimo_conta)
        col_texto.addStretch()

        layout.addLayout(col_texto, 1)

        self.lbl_ultimo_total = QLabel()
        self.lbl_ultimo_total.setMinimumWidth(240)
        self.lbl_ultimo_total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_ultimo_total.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:30px; font-weight:800;
        """)
        layout.addWidget(self.lbl_ultimo_total)

        self._atualizar_ultimo_item()

        return self.cartao_ultimo

    def _construir_linha_cliente(self):

        linha = QFrame()
        linha.setStyleSheet(f"""
            QFrame {{
                background: {tokens.FUNDO};
                border: none;
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(8)

        lbl_icone = QLabel()
        lbl_icone.setStyleSheet("background:transparent;")
        lbl_icone.setPixmap(icone_pixmap("users", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        layout.addWidget(lbl_icone)

        col_cliente = QVBoxLayout()
        col_cliente.setSpacing(0)

        lbl_rotulo = QLabel("CLIENTE")
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)

        self.lbl_cliente = QLabel("Nenhum cliente selecionado")
        self.lbl_cliente.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)

        col_cliente.addWidget(lbl_rotulo)
        col_cliente.addWidget(self.lbl_cliente)

        layout.addLayout(col_cliente)
        layout.addStretch()

        self.bt_limpar_cliente = QPushButton("remover")
        self.bt_limpar_cliente.setCursor(Qt.PointingHandCursor)
        self.bt_limpar_cliente.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.ERRO}; font-size:{tokens.TAMANHO_XS}px;
            }}
        """)
        self.bt_limpar_cliente.clicked.connect(self.limpar_cliente)
        self.bt_limpar_cliente.setVisible(False)
        layout.addWidget(self.bt_limpar_cliente)

        self.bt_selecionar_cliente = QPushButton("F2")
        self.bt_selecionar_cliente.setToolTip("Selecionar cliente (F2)")
        self.bt_selecionar_cliente.setCursor(Qt.PointingHandCursor)
        self.bt_selecionar_cliente.setFocusPolicy(Qt.NoFocus)
        self.bt_selecionar_cliente.setFixedHeight(30)
        self.bt_selecionar_cliente.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; color:{tokens.PRIMARIA};
                border:1px solid {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
                font-size:{tokens.TAMANHO_SM}px; font-weight:800; padding: 0 12px;
            }}
            QPushButton:hover {{ background:{tokens.PRIMARIA_CLARA}; }}
        """)
        self.bt_selecionar_cliente.clicked.connect(self.abrir_selecionar_cliente)
        layout.addWidget(self.bt_selecionar_cliente)

        return linha

    def _construir_mais_vendidos(self):

        self.linha_mais_vendidos = QFrame()
        self.linha_mais_vendidos.setStyleSheet("background:transparent; border:none;")
        self.linha_mais_vendidos.setVisible(False)

        layout = QHBoxLayout(self.linha_mais_vendidos)
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(8)

        lbl_icone = QLabel()
        lbl_icone.setStyleSheet("background:transparent;")
        lbl_icone.setPixmap(icone_pixmap("trending-up", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        layout.addWidget(lbl_icone)

        lbl_titulo = QLabel("Mais vendidos:")
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(lbl_titulo)

        self.layout_chips_mais_vendidos = QHBoxLayout()
        self.layout_chips_mais_vendidos.setSpacing(6)
        layout.addLayout(self.layout_chips_mais_vendidos)

        layout.addStretch()

        return self.linha_mais_vendidos

    def atualizar_mais_vendidos(self):
        """Painel de acesso rápido pros produtos mais vendidos nos
        últimos 30 dias. Usa o relatório de vendas (top_produtos já vem
        agregado pelo banco) em vez de baixar o histórico de vendas
        inteiro pro cliente e somar em Python -- com muitas vendas
        registradas, aquele caminho antigo deixava a abertura do PDV
        visivelmente lenta."""

        while self.layout_chips_mais_vendidos.count():
            item = self.layout_chips_mais_vendidos.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        hoje = datetime.now().date()
        inicio = hoje - timedelta(days=30)

        try:
            relatorio = relatorio_vendas(
                inicio.isoformat(), hoje.isoformat(), limit=1
            )
            produtos = listar_produtos()
        except Exception:
            self.linha_mais_vendidos.setVisible(False)
            return

        produtos_por_nome = {p["nome"]: p for p in produtos}
        top = relatorio.get("top_produtos", [])[:5]
        exibidos = 0

        for entrada in top:

            produto = produtos_por_nome.get(entrada.get("produto"))

            if not produto or not produto.get("ativo", True):
                continue

            chip = BotaoSecundario(produto["nome"][:18])
            chip.setMinimumHeight(30)
            chip.clicked.connect(
                lambda _checked, p=produto: self.adicionar_produto_ao_carrinho(
                    {
                        "id": p["id"],
                        "codigo": p["codigo"],
                        "nome": p["nome"],
                        # preco_efetivo (nao preco_venda): respeita a
                        # promocao vigente, igual a busca normal do PDV
                        # -- o backend recusa preco diferente desse
                        "preco": float(p.get("preco_efetivo", p["preco_venda"])),
                        "estoque": p["estoque"],
                    },
                    1,
                )
            )
            self.layout_chips_mais_vendidos.addWidget(chip)
            exibidos += 1

        self.linha_mais_vendidos.setVisible(exibidos > 0)

    def _construir_cartao_tabela(self):
        """A tabela em si (self.tabela) fica dentro de um Card, mas o
        atributo continua sendo o QTableWidget puro — atualizar_tabela()
        mexe direto nele (setRowCount/setItem/setCellWidget). Alterna
        com um estado vazio (self.pilha_carrinho) quando não há itens,
        pra não deixar um vão em branco atrás da tabela zerada."""

        cartao = QFrame()
        cartao.setObjectName("cartaoCupom")
        cartao.setStyleSheet(f"""
            QFrame#cartaoCupom {{
                background: {tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        layout = QVBoxLayout(cartao)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        cabecalho_tabela = QHBoxLayout()
        cabecalho_tabela.setContentsMargins(16, 14, 16, 10)

        lbl_titulo_tabela = QLabel("CUPOM")
        lbl_titulo_tabela.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:800; letter-spacing: 0.5px;
        """)
        cabecalho_tabela.addWidget(lbl_titulo_tabela)
        cabecalho_tabela.addStretch()

        self.lbl_itens_tabela = QLabel("0 itens")
        self.lbl_itens_tabela.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        cabecalho_tabela.addWidget(self.lbl_itens_tabela)

        self.bt_limpar_carrinho = QPushButton("Limpar carrinho")
        self.bt_limpar_carrinho.setCursor(Qt.PointingHandCursor)
        self.bt_limpar_carrinho.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.ERRO}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:600; margin-left: 14px;
            }}
            QPushButton:hover {{ color:{tokens.ERRO_HOVER}; }}
        """)
        # reaproveita cancelar_venda -- mesma confirmacao, mesmo efeito
        # de esvaziar o carrinho; so' um atalho visual mais perto de
        # onde o operador esta' olhando (o contador de itens)
        self.bt_limpar_carrinho.clicked.connect(self.cancelar_venda)
        self.bt_limpar_carrinho.setVisible(False)
        cabecalho_tabela.addWidget(self.bt_limpar_carrinho)

        layout.addLayout(cabecalho_tabela)

        self.pilha_carrinho = QStackedWidget()
        self.pilha_carrinho.setStyleSheet("background:transparent;")

        self.pilha_carrinho.addWidget(self._construir_estado_vazio_carrinho())

        self.tabela = QTableWidget()

        # formato de cupom: linhas simples, sem botao por linha --
        # quantidade e remocao sao pelo teclado (+ / - / Del) no item
        # selecionado (ver eventFilter), como nos PDVs de loja
        self.tabela.setColumnCount(6)

        self.tabela.setHorizontalHeaderLabels([
            "Nº",
            "Código",
            "Produto",
            "Qtd",
            "Unitário",
            "Total",
        ])

        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setSelectionMode(QTableWidget.SingleSelection)
        self.tabela.setSelectionBehavior(QTableWidget.SelectRows)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setShowGrid(False)
        self.tabela.verticalHeader().setDefaultSectionSize(40)

        cabecalho_horizontal = self.tabela.horizontalHeader()
        cabecalho_horizontal.setStretchLastSection(False)
        cabecalho_horizontal.setSectionResizeMode(2, QHeaderView.Stretch)
        self.tabela.setColumnWidth(0, 56)
        self.tabela.setColumnWidth(1, 140)
        self.tabela.setColumnWidth(3, 70)
        self.tabela.setColumnWidth(4, 110)
        self.tabela.setColumnWidth(5, 120)
        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                border: none;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                font-size: {tokens.TAMANHO_MD}px;
                alternate-background-color: {tokens.FUNDO};
                selection-background-color: {tokens.PRIMARIA_CLARA};
                selection-color: {tokens.TEXTO};
            }}
            QHeaderView::section {{
                background: {tokens.CARD};
                color: {tokens.TEXTO_SECUNDARIO};
                font-weight: 700;
                font-size: {tokens.TAMANHO_XS}px;
                padding: 10px 8px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
            QTableWidget::item {{
                border: none;
                padding: 4px;
            }}
        """)
        self.tabela.setAlternatingRowColors(True)

        self.pilha_carrinho.addWidget(self.tabela)
        self.pilha_carrinho.setCurrentIndex(0)

        layout.addWidget(self.pilha_carrinho, stretch=1)

        return cartao

    def _construir_estado_vazio_carrinho(self):

        estado = QWidget()
        estado.setStyleSheet("background:transparent;")

        layout = QVBoxLayout(estado)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(6)

        lbl_titulo = QLabel("CAIXA LIVRE")
        lbl_titulo.setAlignment(Qt.AlignCenter)
        lbl_titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.SECUNDARIA};
            font-size:56px; font-weight:900; letter-spacing: 4px;
        """)
        layout.addWidget(lbl_titulo)

        lbl_dica = QLabel(
            "Passe o código de barras ou pressione "
            f"{self.atalhos['busca']} para buscar pelo nome."
        )
        lbl_dica.setAlignment(Qt.AlignCenter)
        lbl_dica.setWordWrap(True)
        lbl_dica.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        lbl_dica.setMaximumWidth(420)
        layout.addWidget(lbl_dica, alignment=Qt.AlignCenter)

        return estado

    def _linha_resumo(self, rotulo):
        """Uma linha "rótulo ..... valor" do card de resumo — devolve o
        QLabel do valor pra poder atualizar depois."""

        linha = QHBoxLayout()
        linha.setSpacing(8)

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)

        lbl_valor = QLabel("R$ 0,00")
        lbl_valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)

        linha.addWidget(lbl_rotulo)
        linha.addStretch()
        linha.addWidget(lbl_valor)

        return linha, lbl_valor

    def _construir_cartao_resumo(self):

        cartao = QFrame()
        cartao.setObjectName("cartaoResumoVenda")
        cartao.setStyleSheet(f"""
            QFrame#cartaoResumoVenda {{
                background: {tokens.CARD};
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_LG}px;
            }}
        """)

        layout = QVBoxLayout(cartao)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(self._construir_linha_cliente())

        titulo = QLabel("RESUMO DA VENDA")
        titulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800; letter-spacing: 0.5px;
        """)
        layout.addWidget(titulo)

        linha_itens, self.lbl_itens_valor = self._linha_resumo("Itens")
        self.lbl_itens_valor.setText("0")
        layout.addLayout(linha_itens)

        linha_subtotal, self.lbl_subtotal_valor = self._linha_resumo("Subtotal")
        layout.addLayout(linha_subtotal)

        # ------ desconto / acréscimo (recolhido por padrão) ------

        linha_ajuste_botoes = QHBoxLayout()
        linha_ajuste_botoes.setSpacing(18)

        estilo_bt_ajuste = f"""
            QPushButton {{
                background:transparent; border:none; text-align:left;
                color:{tokens.PRIMARIA}; font-size:{tokens.TAMANHO_SM}px;
                font-weight:600; padding: 2px 0;
            }}
        """

        self.bt_alternar_ajuste = QPushButton("+ Desconto (F6)")
        self.bt_alternar_ajuste.setCursor(Qt.PointingHandCursor)
        self.bt_alternar_ajuste.setStyleSheet(estilo_bt_ajuste)
        self.bt_alternar_ajuste.clicked.connect(self._alternar_bloco_ajuste)

        self.bt_alternar_acrescimo = QPushButton("+ Acréscimo (F7)")
        self.bt_alternar_acrescimo.setCursor(Qt.PointingHandCursor)
        self.bt_alternar_acrescimo.setStyleSheet(estilo_bt_ajuste)
        self.bt_alternar_acrescimo.clicked.connect(self._abrir_ajuste_acrescimo)

        linha_ajuste_botoes.addWidget(self.bt_alternar_ajuste)
        linha_ajuste_botoes.addWidget(self.bt_alternar_acrescimo)
        linha_ajuste_botoes.addStretch()

        layout.addLayout(linha_ajuste_botoes)

        self.bloco_ajuste = QFrame()
        self.bloco_ajuste.setVisible(False)
        self.bloco_ajuste.setStyleSheet(f"""
            QFrame {{
                background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
            }}
        """)

        ajuste_layout = QHBoxLayout(self.bloco_ajuste)
        ajuste_layout.setContentsMargins(14, 12, 14, 12)
        ajuste_layout.setSpacing(12)

        col_desconto = QVBoxLayout()
        col_desconto.setSpacing(4)
        lbl_desconto = QLabel("DESCONTO (R$)")
        lbl_desconto.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)
        self.campo_desconto = CampoTexto("0,00")
        self.campo_desconto.textChanged.connect(self._recalcular_totais)
        col_desconto.addWidget(lbl_desconto)
        col_desconto.addWidget(self.campo_desconto)

        col_acrescimo = QVBoxLayout()
        col_acrescimo.setSpacing(4)
        lbl_acrescimo = QLabel("ACRÉSCIMO (R$)")
        lbl_acrescimo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:700;
        """)
        self.campo_acrescimo = CampoTexto("0,00")
        self.campo_acrescimo.textChanged.connect(self._recalcular_totais)
        col_acrescimo.addWidget(lbl_acrescimo)
        col_acrescimo.addWidget(self.campo_acrescimo)

        ajuste_layout.addLayout(col_desconto)
        ajuste_layout.addLayout(col_acrescimo)

        layout.addWidget(self.bloco_ajuste)

        linha_desconto, self.lbl_desconto_valor = self._linha_resumo("Desconto")
        layout.addLayout(linha_desconto)

        linha_acrescimo, self.lbl_acrescimo_valor = self._linha_resumo("Acréscimo")
        layout.addLayout(linha_acrescimo)

        # total ancorado embaixo, colado no botao Finalizar -- o espaco
        # que sobra fica entre o detalhamento e o total
        layout.addStretch()

        caixa_total = QFrame()
        caixa_total.setStyleSheet(f"""
            QFrame {{
                background: {tokens.SUCESSO_CLARO};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

        layout_caixa_total = QVBoxLayout(caixa_total)
        layout_caixa_total.setContentsMargins(16, 14, 16, 16)
        layout_caixa_total.setSpacing(2)

        lbl_total_rotulo = QLabel("TOTAL")
        lbl_total_rotulo.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_XS}px; font-weight:800; letter-spacing: 0.5px;
        """)
        layout_caixa_total.addWidget(lbl_total_rotulo)

        self.total = QLabel("R$ 0,00")
        self.total.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.total.setStyleSheet(f"""
            background:transparent; font-size: 50px; font-weight: 900;
            color: {tokens.SECUNDARIA};
        """)
        layout_caixa_total.addWidget(self.total)

        layout.addWidget(caixa_total)

        return cartao

    def _construir_botao_pagar(self):

        self.bt_pagar = BotaoSucesso("Finalizar Venda (F3)", icone_nome="credit-card")
        self.bt_pagar.setMinimumHeight(58)
        self.bt_pagar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.bt_pagar.clicked.connect(self.finalizar_venda)

        return self.bt_pagar

    # ==================================================
    # INDICADOR DE CAIXA ABERTO
    # ==================================================

    def atualizar_indicador_caixa(self):

        info = caixa_aberto()

        if not info:
            self.badge_caixa.setText("Caixa fechado")
            self.badge_caixa.setStyleSheet(f"""
                background: {tokens.ERRO_CLARO}; color: {tokens.ERRO_HOVER};
                border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
                font-weight: 600; padding: 3px 10px;
            """)
            return

        abertura = _parse_data(info.get("data_abertura"))
        hora_texto = abertura.strftime("%H:%M") if abertura else "—"

        self.badge_caixa.setText(f"Caixa aberto às {hora_texto}")
        self.badge_caixa.setStyleSheet(f"""
            background: {tokens.SUCESSO_CLARO}; color: {tokens.SECUNDARIA_HOVER};
            border-radius: {tokens.RADIUS_PILL}px; font-size: {tokens.TAMANHO_XS}px;
            font-weight: 600; padding: 3px 10px;
        """)

    # ==================================================
    # CÓDIGO DE BARRAS (campo gigante)
    # ==================================================

    def processar_codigo(self):

        codigo = self.campo_codigo.text().strip()

        if not codigo:
            return

        quantidade, codigo = _separar_multiplicador(codigo)

        if not codigo:
            return  # so' "3*" -- espera o codigo

        produto = buscar_produto(codigo)

        if produto is None:
            self._mostrar_status_busca(f"Produto não encontrado: {codigo}", erro=True)
            self.campo_codigo.selectAll()
            return

        if not self.adicionar_produto_ao_carrinho(produto, quantidade):
            self.campo_codigo.selectAll()
            return

        self.campo_codigo.clear()

    def _atualizar_multiplicador(self, texto):

        quantidade, _ = _separar_multiplicador(texto.strip())
        tem_multiplicador = "*" in texto and quantidade > 1

        self.lbl_multiplicador.setText(f"× {quantidade}")
        self.lbl_multiplicador.setVisible(tem_multiplicador)

    def _mostrar_status_busca(self, texto, erro):

        cor = tokens.ERRO if erro else tokens.SECUNDARIA
        self.lbl_status_busca.setStyleSheet(f"""
            background:transparent; color:{cor};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        self.lbl_status_busca.setText(texto)

        QTimer.singleShot(
            2500,
            lambda: (
                self.lbl_status_busca.setText("")
                if self.lbl_status_busca.text() == texto else None
            ),
        )

    # ==================================================
    # BUSCAR PRODUTO (F1) - abre o modal de pesquisa
    # ==================================================

    def abrir_busca(self):

        dialog = BuscarProdutoDialog(self)
        dialog.produto_selecionado.connect(
            self.adicionar_produto_ao_carrinho
        )
        dialog.exec()

    def adicionar_produto_ao_carrinho(self, produto, quantidade):

        item_existente = next(
            (item for item in self.itens if item["id"] == produto["id"]),
            None,
        )

        no_carrinho = item_existente["quantidade"] if item_existente else 0
        estoque = produto.get("estoque")

        # estoque None = dado nao veio junto (nao deveria acontecer,
        # mas nao trava a venda por causa disso - so pula a checagem)
        if estoque is not None and no_carrinho + quantidade > estoque:

            if estoque <= 0:
                mensagem = f"{produto['nome']} está sem estoque disponível."
            elif no_carrinho > 0:
                mensagem = (
                    f"Estoque insuficiente de {produto['nome']} — "
                    f"disponível: {estoque}, já no carrinho: {no_carrinho}."
                )
            else:
                mensagem = (
                    f"Estoque insuficiente de {produto['nome']} — "
                    f"disponível: {estoque}."
                )

            self._mostrar_status_busca(mensagem, erro=True)
            return False

        if item_existente:
            item_existente["quantidade"] += quantidade
        else:
            self.itens.append(
                {
                    "id": produto["id"],
                    "codigo": produto["codigo"],
                    "nome": produto["nome"],
                    "preco": float(produto["preco"]),
                    "quantidade": quantidade,
                    "estoque": estoque,
                    "tem_foto": produto.get("tem_foto", False),
                }
            )

        self._id_ultimo_item = produto["id"]
        self.atualizar_tabela()
        return True

    # ==================================================
    # NOVO PRODUTO (F4) - cadastro completo sem sair do PDV
    # ==================================================

    def abrir_novo_produto(self):

        dialog = CadastroProdutoWindow()

        if dialog.exec() != QDialog.Accepted:
            return

        response = cadastrar_produto(dialog.dados)

        if response.status_code != 201:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro", str(erro))
            return

        produto_criado = response.json()

        # a resposta do cadastro vem no formato "cru" (preco_venda) --
        # o carrinho espera o formato do PDV (preco), entao rebusca
        # pelo codigo pra pegar exatamente o mesmo shape que o F1/scanner usa
        codigo = (
            produto_criado.get("codigo_barras")
            or produto_criado.get("codigo")
        )

        produto = buscar_produto(codigo)

        if produto is None:
            return

        self.adicionar_produto_ao_carrinho(produto, 1)
        self._mostrar_status_busca(
            f"Produto cadastrado e adicionado: {produto['nome']}",
            erro=False,
        )

    # ==================================================
    # CLIENTE (opcional, vale pra qualquer forma de pagamento)
    # ==================================================

    def abrir_selecionar_cliente(self):

        dialogo = SelecionarClienteDialog(self)
        dialogo.cliente_selecionado.connect(self.definir_cliente)
        dialogo.exec()

    def definir_cliente(self, cliente):

        self.cliente_id = cliente["id"]
        self.cliente_nome = cliente["nome"]

        self.lbl_cliente.setText(cliente["nome"])
        self.lbl_cliente.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        self.bt_limpar_cliente.setVisible(True)

    def limpar_cliente(self):

        self.cliente_id = None
        self.cliente_nome = None

        self.lbl_cliente.setText("Nenhum cliente selecionado")
        self.lbl_cliente.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_TERCIARIO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:600;
        """)
        self.bt_limpar_cliente.setVisible(False)

    # ==================================================
    # DESCONTO / ACRÉSCIMO
    # ==================================================

    def _alternar_bloco_ajuste(self):
        self.bloco_ajuste.setVisible(not self.bloco_ajuste.isVisible())
        if self.bloco_ajuste.isVisible():
            self.campo_desconto.setFocus()
            self.campo_desconto.selectAll()

    def _abrir_ajuste_acrescimo(self):
        # sempre abre (nao alterna) -- F7 e' "eu quero mexer no
        # acrescimo agora", nao "esconde se ja tiver aberto"
        self.bloco_ajuste.setVisible(True)
        self.campo_acrescimo.setFocus()
        self.campo_acrescimo.selectAll()

    # ==================================================
    # ATUALIZAR TABELA / TOTAIS
    # ==================================================

    def atualizar_tabela(self):

        self.tabela.setRowCount(len(self.itens))

        alinhado_direita = Qt.AlignRight | Qt.AlignVCenter
        linha_ultimo = None

        for linha, item in enumerate(self.itens):
            subtotal = item["preco"] * item["quantidade"]

            celulas = [
                (f"{linha + 1:03d}", Qt.AlignCenter),
                (item["codigo"], Qt.AlignLeft | Qt.AlignVCenter),
                (item["nome"], Qt.AlignLeft | Qt.AlignVCenter),
                (str(item["quantidade"]), Qt.AlignCenter),
                (formatar_moeda(item["preco"]), alinhado_direita),
                (formatar_moeda(subtotal), alinhado_direita),
            ]

            for coluna, (texto, alinhamento) in enumerate(celulas):
                celula = QTableWidgetItem(texto)
                celula.setTextAlignment(alinhamento)
                if coluna in (2, 5):
                    fonte = celula.font()
                    fonte.setBold(True)
                    celula.setFont(fonte)
                self.tabela.setItem(linha, coluna, celula)

            if item["id"] == self._id_ultimo_item:
                linha_ultimo = linha

        if self.itens:
            if linha_ultimo is None:
                linha_ultimo = len(self.itens) - 1
                self._id_ultimo_item = self.itens[-1]["id"]
            self.tabela.selectRow(linha_ultimo)
            self.tabela.scrollToItem(self.tabela.item(linha_ultimo, 0))
        else:
            self._id_ultimo_item = None

        self.pilha_carrinho.setCurrentWidget(
            self.tabela if self.itens else self.pilha_carrinho.widget(0)
        )
        self.bt_limpar_carrinho.setVisible(bool(self.itens))

        self._atualizar_ultimo_item()
        self._recalcular_totais()
        self.campo_codigo.setFocus()

    # ==================================================
    # DESTAQUE DO ÚLTIMO ITEM
    # ==================================================

    def _atualizar_ultimo_item(self):

        item = next(
            (i for i in self.itens if i["id"] == self._id_ultimo_item), None
        )

        if item is None:
            self.lbl_ultimo_rotulo.setText("")
            self.lbl_ultimo_nome.setText("Aguardando produto...")
            self.lbl_ultimo_nome.setStyleSheet(f"""
                background:transparent; color:{tokens.TEXTO_TERCIARIO};
                font-size:24px; font-weight:800;
            """)
            self.lbl_ultimo_conta.setText("")
            self.lbl_ultimo_total.setText("")
            self._exibir_monograma_ultimo(None)
            return

        self.lbl_ultimo_rotulo.setText("ÚLTIMO ITEM")
        self.lbl_ultimo_nome.setText(item["nome"])
        self.lbl_ultimo_nome.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:24px; font-weight:800;
        """)
        self.lbl_ultimo_conta.setText(
            f"{item['quantidade']} × {formatar_moeda(item['preco'])}"
        )
        self.lbl_ultimo_total.setText(
            formatar_moeda(item["preco"] * item["quantidade"])
        )

        foto = self._fotos_cache.get(item["id"])

        if foto:
            self._exibir_foto_ultimo(foto)
            return

        self._exibir_monograma_ultimo(item["nome"])

        if item.get("tem_foto") and item["id"] not in self._fotos_cache:
            # marca como "buscando" pra nao disparar de novo a cada
            # atualizacao enquanto a foto baixa
            self._fotos_cache[item["id"]] = None
            rodar_em_thread(
                self,
                _baixar_foto_com_id,
                item["id"],
                ao_sucesso=self._ao_baixar_foto_ultimo,
                ao_erro=self._ignorar_erro,
            )

    def _ao_baixar_foto_ultimo(self, resultado):

        produto_id, foto = resultado

        if not foto:
            return

        self._fotos_cache[produto_id] = foto

        if produto_id == self._id_ultimo_item:
            self._exibir_foto_ultimo(foto)

    def _exibir_foto_ultimo(self, foto):

        pixmap = QPixmap()

        if not pixmap.loadFromData(foto):
            return

        self.lbl_ultimo_foto.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
        """)
        self.lbl_ultimo_foto.setPixmap(
            pixmap.scaled(86, 86, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )

    def _exibir_monograma_ultimo(self, nome):
        """Inicial colorida quando o produto nao tem foto (mesmo
        principio dos avatares de Clientes Recentes do Dashboard)."""

        self.lbl_ultimo_foto.clear()

        if not nome:
            self.lbl_ultimo_foto.setText("")
            self.lbl_ultimo_foto.setStyleSheet(f"""
                background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px;
            """)
            self.lbl_ultimo_foto.setPixmap(
                icone_pixmap("shopping-cart", cor=tokens.TEXTO_TERCIARIO, tamanho=32)
            )
            return

        cor = _CORES_MONOGRAMA[sum(ord(c) for c in nome) % len(_CORES_MONOGRAMA)]

        self.lbl_ultimo_foto.setText((nome[:1] or "?").upper())
        self.lbl_ultimo_foto.setStyleSheet(f"""
            background:{cor}; color:white; border-radius:{tokens.RADIUS_SM}px;
            font-size:36px; font-weight:900;
        """)

    # ==================================================
    # TECLADO NO CUPOM (Del / + / - / setas)
    # ==================================================

    def eventFilter(self, origem, evento):

        if evento.type() != QEvent.KeyPress or not self.itens:
            return super().eventFilter(origem, evento)

        tecla = evento.key()
        no_campo = origem is self.campo_codigo
        campo_vazio = not self.campo_codigo.text().strip()

        if tecla in (Qt.Key_Up, Qt.Key_Down):
            linha = self._linha_selecionada()
            passo = -1 if tecla == Qt.Key_Up else 1
            nova = max(0, min(len(self.itens) - 1, linha + passo))
            self.tabela.selectRow(nova)
            self._id_ultimo_item = self.itens[nova]["id"]
            self._atualizar_ultimo_item()
            return True

        # no campo de codigo, Del/+/- so' valem com o campo vazio --
        # com texto, sao edicao normal do que esta' sendo digitado
        if no_campo and not campo_vazio:
            return super().eventFilter(origem, evento)

        if tecla == Qt.Key_Delete:
            self.remover_item(self._linha_selecionada())
            return True

        if tecla == Qt.Key_Plus:
            self.alterar_quantidade(self._linha_selecionada(), 1)
            return True

        if tecla == Qt.Key_Minus:
            self.alterar_quantidade(self._linha_selecionada(), -1)
            return True

        return super().eventFilter(origem, evento)

    def _linha_selecionada(self):

        linhas = self.tabela.selectionModel().selectedRows()

        if linhas:
            return linhas[0].row()

        return len(self.itens) - 1

    def _recalcular_totais(self):

        subtotal = sum(item["preco"] * item["quantidade"] for item in self.itens)

        self.desconto_valor = _parse_valor(self.campo_desconto.text())
        self.acrescimo_valor = _parse_valor(self.campo_acrescimo.text())

        # guarda o valor sem o "piso" em zero -- e' o que de fato vai
        # pro backend (ver finalizar_venda); o max(0, ...) abaixo e' so
        # pra exibicao, senao um desconto digitado errado por engano
        # mostraria "R$ 0,00" como se fosse valido e a venda seria
        # recusada so depois de abrir a tela de pagamento inteira
        self._total_bruto = (
            subtotal - self.desconto_valor + self.acrescimo_valor
        )

        total = max(0.0, self._total_bruto)

        self.lbl_itens_valor.setText(str(len(self.itens)))
        self.lbl_itens_tabela.setText(
            "1 item" if len(self.itens) == 1 else f"{len(self.itens)} itens"
        )
        self.lbl_subtotal_valor.setText(formatar_moeda(subtotal))

        self.lbl_desconto_valor.setText(
            f"- {formatar_moeda(self.desconto_valor)}"
            if self.desconto_valor else formatar_moeda(0)
        )
        self.lbl_desconto_valor.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            color: {tokens.ERRO if self.desconto_valor else tokens.TEXTO};
        """)

        self.lbl_acrescimo_valor.setText(
            f"+ {formatar_moeda(self.acrescimo_valor)}"
            if self.acrescimo_valor else formatar_moeda(0)
        )
        self.lbl_acrescimo_valor.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_SM}px; font-weight:700;
            color: {tokens.SECUNDARIA if self.acrescimo_valor else tokens.TEXTO};
        """)

        self.total.setText(formatar_moeda(total))

        return total

    # ==================================================
    # QUANTIDADE / REMOVER (item selecionado do cupom)
    # ==================================================

    def alterar_quantidade(self, linha, delta):

        if linha >= len(self.itens):
            return

        item = self.itens[linha]
        nova_quantidade = item["quantidade"] + delta

        if nova_quantidade <= 0:
            self.remover_item(linha)
            return

        estoque = item.get("estoque")

        if delta > 0 and estoque is not None and nova_quantidade > estoque:
            self._mostrar_status_busca(
                f"Estoque insuficiente de {item['nome']} — "
                f"disponível: {estoque}.",
                erro=True,
            )
            return

        item["quantidade"] = nova_quantidade
        self._id_ultimo_item = item["id"]

        self.atualizar_tabela()

    def remover_item(self, linha):

        if linha < 0 or linha >= len(self.itens):
            return

        del self.itens[linha]

        # selecao/destaque vao pro item que ficou no lugar (ou o de
        # cima, se era o ultimo) -- Del seguido de Del vai limpando
        if self.itens:
            self._id_ultimo_item = self.itens[min(linha, len(self.itens) - 1)]["id"]

        self.atualizar_tabela()

    # ==================================================
    # CANCELAR VENDA
    # ==================================================

    def cancelar_venda(self):

        if not self.itens:
            return

        resposta = QMessageBox.question(
            self,
            "Cancelar Venda",
            "Deseja cancelar esta venda?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if resposta == QMessageBox.No:
            return

        self.limpar_venda()

    def limpar_venda(self):

        self._chave_venda = None
        self.itens.clear()
        self._id_ultimo_item = None
        self._atualizar_ultimo_item()

        self.tabela.setRowCount(0)
        self.pilha_carrinho.setCurrentWidget(self.pilha_carrinho.widget(0))

        self.limpar_cliente()

        self.campo_desconto.setText("")
        self.campo_acrescimo.setText("")
        self.bloco_ajuste.setVisible(False)

        self.lbl_itens_valor.setText("0")
        self.lbl_itens_tabela.setText("0 itens")
        self.lbl_subtotal_valor.setText(formatar_moeda(0))
        self.lbl_desconto_valor.setText(formatar_moeda(0))
        self.lbl_acrescimo_valor.setText(formatar_moeda(0))
        self.lbl_desconto_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)
        self.lbl_acrescimo_valor.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO};
            font-size:{tokens.TAMANHO_SM}px; font-weight:700;
        """)

        self.total.setText("R$ 0,00")

        self.campo_codigo.setFocus()

    # ==================================================
    # VENDA SUSPENSA (pré-venda) — persistida no backend como
    # Venda.status=ABERTA (ver VendaService.suspender/listar_suspensas/
    # excluir_suspensa): sobrevive a fechar o app e aparece pra
    # qualquer terminal logado na mesma loja, não só neste PDV.
    # ==================================================

    def suspender_venda(self):

        if self._suspendendo_venda:
            return

        if not self.itens:
            QMessageBox.warning(
                self, "Aviso", "Não há itens no carrinho pra suspender."
            )
            return

        self._suspendendo_venda = True
        self.bt_suspender.setEnabled(False)
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        desconto_liquido = self.desconto_valor - self.acrescimo_valor

        rodar_em_thread(
            self,
            enviar_suspensao,
            self.itens,
            cliente_id=self.cliente_id,
            desconto=desconto_liquido,
            ao_sucesso=self._ao_suspender_sucesso,
            ao_erro=self._ao_suspender_erro,
            ao_finalizar=self._ao_suspender_finalizada,
        )

    def _ao_suspender_sucesso(self, response):

        if response.status_code != 201:

            try:
                erro = response.json()
                erro = erro.get("detail", str(erro)) if isinstance(erro, dict) else erro
            except Exception:
                erro = response.text

            QMessageBox.critical(
                self, "Erro", f"Não foi possível suspender a venda.\n\n{erro}"
            )
            return

        self.limpar_venda()
        self._atualizar_contagem_suspensas()

        QMessageBox.information(
            self,
            "Venda suspensa",
            'Use "Vendas Suspensas" pra retomar de onde parou.',
        )

    def _ao_suspender_erro(self, erro):
        QMessageBox.critical(self, "Erro", str(erro))

    def _ao_suspender_finalizada(self):
        self._suspendendo_venda = False
        self.bt_suspender.setEnabled(True)
        QApplication.restoreOverrideCursor()

    def abrir_vendas_suspensas(self):

        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        rodar_em_thread(
            self,
            listar_vendas_suspensas,
            ao_sucesso=self._ao_listar_suspensas_sucesso,
            ao_erro=self._ao_listar_suspensas_erro,
            ao_finalizar=self._ao_listar_suspensas_finalizada,
        )

    def _ao_listar_suspensas_finalizada(self):
        QApplication.restoreOverrideCursor()

    def _ao_listar_suspensas_erro(self, erro):
        QMessageBox.critical(
            self, "Erro", f"Não foi possível carregar as vendas suspensas.\n{erro}"
        )

    def _ao_listar_suspensas_sucesso(self, vendas_suspensas):

        dialogo = VendasSuspensasDialog(vendas_suspensas, parent=self)

        if dialogo.exec() != QDialog.Accepted or dialogo.indice_selecionado is None:
            return

        venda = vendas_suspensas[dialogo.indice_selecionado]

        if dialogo.acao == "excluir":
            rodar_em_thread(
                self,
                excluir_venda_suspensa,
                venda["id"],
                ao_sucesso=self._ao_excluir_suspensa_manual_sucesso,
                ao_erro=self._ao_listar_suspensas_erro,
            )
            return

        if self.itens:
            QMessageBox.warning(
                self,
                "Aviso",
                "Finalize, cancele ou suspenda a venda atual antes de "
                "retomar outra.",
            )
            return

        # "codigo"/"estoque" vem None quando o produto foi excluido
        # depois da venda ter sido suspensa -- QTableWidgetItem(None)
        # quebra, e o proprio atualizar_tabela/checagem de estoque
        # esperam string/int normais
        self.itens = [
            {
                "id": item["produto_id"],
                "codigo": item["codigo"] or "",
                "nome": item["nome"],
                "preco": float(item["valor_unitario"]),
                "quantidade": item["quantidade"],
                "estoque": item["estoque"] or 0,
            }
            for item in venda["itens"]
        ]
        self.atualizar_tabela()

        if venda["cliente_id"]:
            self.definir_cliente({
                "id": venda["cliente_id"],
                "nome": venda["cliente_nome"],
            })
        else:
            self.limpar_cliente()

        desconto_liquido = float(venda["desconto"])
        self.campo_desconto.setText(
            f"{desconto_liquido:.2f}" if desconto_liquido >= 0 else ""
        )
        self.campo_acrescimo.setText(
            f"{-desconto_liquido:.2f}" if desconto_liquido < 0 else ""
        )
        self.bloco_ajuste.setVisible(desconto_liquido != 0)

        # a venda ja foi retomada pro carrinho local -- apaga o
        # rascunho no servidor pra nao ficar duplicada na lista (falha
        # aqui nao desfaz a retomada, so' deixa o rascunho orfao pra
        # ser limpo manualmente depois, daí o erro silencioso)
        rodar_em_thread(
            self,
            excluir_venda_suspensa,
            venda["id"],
            ao_sucesso=self._ao_excluir_suspensa_sucesso,
            ao_erro=self._ignorar_erro,
        )

    def _ao_excluir_suspensa_manual_sucesso(self, response):

        if response.status_code != 200:
            try:
                erro = response.json()
                erro = erro.get("detail", str(erro)) if isinstance(erro, dict) else erro
            except Exception:
                erro = response.text

            QMessageBox.critical(
                self, "Erro", f"Não foi possível excluir a venda suspensa.\n\n{erro}"
            )
            return

        self._atualizar_contagem_suspensas()

    def _ao_excluir_suspensa_sucesso(self, response):
        # cleanup silencioso do rascunho apos retomar (ver
        # _ao_listar_suspensas_sucesso) -- diferente do handler acima,
        # nao mostra erro pro usuario mesmo se o delete falhar
        self._atualizar_contagem_suspensas()

    def _ignorar_erro(self, erro):
        pass

    def _atualizar_contagem_suspensas(self):

        rodar_em_thread(
            self,
            listar_vendas_suspensas,
            ao_sucesso=self._ao_atualizar_contagem_suspensas_sucesso,
            ao_erro=self._ignorar_erro,
        )

    def _ao_atualizar_contagem_suspensas_sucesso(self, vendas_suspensas):

        total = len(vendas_suspensas)

        self.bt_retomar.setText(
            f"Vendas Suspensas ({total})" if total else "Vendas Suspensas"
        )
        self.bt_retomar.setEnabled(total > 0)

    # ==================================================
    # ORÇAMENTO — imprime/exporta o carrinho atual sem finalizar a
    # venda. Não fica salvo nem listável em nenhum lugar: se virar
    # venda de verdade, é só continuar normalmente e ir em "Pagar".
    # ==================================================

    def imprimir_orcamento(self):

        if not self.itens:
            QMessageBox.warning(
                self, "Aviso", "Não há itens no carrinho pra gerar um orçamento."
            )
            return

        documento = self._montar_documento_orcamento()

        janela = QDialog(self)
        janela.setWindowTitle("Orçamento")
        janela.setFixedSize(360, 230)
        janela.setStyleSheet(f"background:{tokens.FUNDO};")

        layout = QVBoxLayout(janela)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        lbl = QLabel(
            "O orçamento não gera nenhuma venda — é só um documento "
            "pra levar ou enviar ao cliente."
        )
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"""
            background:transparent; color:{tokens.TEXTO_SECUNDARIO};
            font-size:{tokens.TAMANHO_SM}px;
        """)
        layout.addWidget(lbl)

        bt_imprimir = BotaoPrimario("Imprimir", icone_nome="printer")
        bt_imprimir.clicked.connect(
            lambda: self._imprimir_documento(documento, janela)
        )

        bt_pdf = BotaoSecundario("Salvar PDF")
        bt_pdf.clicked.connect(lambda: self._salvar_pdf_documento(documento))

        bt_fechar = BotaoSecundario("Fechar")
        bt_fechar.clicked.connect(janela.accept)

        layout.addWidget(bt_imprimir)
        layout.addWidget(bt_pdf)
        layout.addWidget(bt_fechar)

        janela.exec()

    def _montar_documento_orcamento(self):

        config = configuracoes()
        logo_bytes = comprovante_service.obter_logo_loja()

        subtotal = sum(item["preco"] * item["quantidade"] for item in self.itens)
        total = max(0.0, subtotal - self.desconto_valor + self.acrescimo_valor)

        linhas_itens = "".join(
            linha_zebra(
                [
                    item["nome"],
                    item["quantidade"],
                    formatar_moeda(item["preco"]),
                    formatar_moeda(item["preco"] * item["quantidade"]),
                ],
                indice,
                alinhamentos=["left", "center", "right", "right"],
            )
            for indice, item in enumerate(self.itens)
        )

        cliente_linha = (
            f"<p style='margin:4px 0;'>Cliente: {self.cliente_nome}</p>"
            if self.cliente_nome else ""
        )

        html = f"""
        <html>
        <body style="{ESTILO_BODY}">
            {cabecalho_html("ORÇAMENTO", config, logo_bytes)}
            <p style="margin:4px 0;">
                Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}
            </p>
            {cliente_linha}
            <table style="width:100%; border-collapse:collapse; border:1px solid #E5E7EB; margin-top:12px;">
                {cabecalho_tabela(
                    ["Produto", "Qtd", "Unitário", "Subtotal"],
                    ["left", "center", "right", "right"],
                )}
                {linhas_itens}
            </table>
            {bloco_total("TOTAL", formatar_moeda(total))}
            {rodape_nao_fiscal(
                "Este orçamento não tem valor fiscal e não gera nenhuma "
                "venda. Os valores podem mudar até a confirmação da compra."
            )}
        </body>
        </html>
        """

        documento = QTextDocument()
        documento.setHtml(html)

        return documento

    def _imprimir_documento(self, documento, parent):

        printer = QPrinter(QPrinter.HighResolution)
        dialogo = QPrintDialog(printer, parent)

        if dialogo.exec() != QPrintDialog.Accepted:
            return

        documento.print_(printer)

    def _salvar_pdf_documento(self, documento):

        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar Orçamento", "orcamento.pdf", "Arquivo PDF (*.pdf)",
        )

        if not caminho:
            return

        if not caminho.lower().endswith(".pdf"):
            caminho += ".pdf"

        printer = QPrinter(QPrinter.HighResolution)
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(caminho)

        documento.print_(printer)

        QMessageBox.information(
            self, "Sucesso", "Orçamento salvo em PDF com sucesso."
        )

    # ==================================================
    # FINALIZAR VENDA (PAGAR - F3)
    # ==================================================

    def finalizar_venda(self):

        # Trava de reentrância: bloqueia clique duplo no botão e F3
        # repetido (o atalho global em principal.py chama este mesmo
        # método) enquanto uma venda já está em andamento -- sem isso,
        # um duplo clique durante a resposta lenta do servidor (ex.:
        # modo Terminal, multi-dispositivo) podia disparar duas vendas
        # pro mesmo carrinho.
        if self._finalizando_venda:
            return

        if not self.itens:
            QMessageBox.warning(
                self,
                "Aviso",
                "Nenhum produto foi adicionado."
            )

            return

        total = self._recalcular_totais()

        if self._total_bruto < 0:
            QMessageBox.warning(
                self,
                "Aviso",
                "O desconto não pode ser maior que o total da venda."
            )
            return

        # PagamentoWindow e' so' local (forma de pagamento, troco...),
        # sem chamada de rede -- fica sincrono/modal mesmo, so' a
        # submissao da venda em si (dali pra baixo) vai pra thread.
        tela = PagamentoWindow(
            total,
            self.itens,
            cliente_id=self.cliente_id,
            cliente_nome=self.cliente_nome,
            desconto=self.desconto_valor,
            acrescimo=self.acrescimo_valor,
        )

        if tela.exec() != QDialog.Accepted:
            return

        # sem UI otimista aqui de proposito: venda envolve dinheiro e
        # baixa de estoque de verdade no servidor, nao tem "desfazer"
        # seguro no cliente -- a tela so' mostra "venda concluida"
        # depois que o 201 realmente voltar.
        self._finalizando_venda = True
        self.bt_pagar.setEnabled(False)
        QApplication.setOverrideCursor(QCursor(Qt.WaitCursor))

        self._venda_pagamento_tela = tela
        self._venda_total_em_andamento = total

        desconto_liquido = self.desconto_valor - self.acrescimo_valor

        # Mesma chave em todo reenvio deste carrinho: se a resposta se
        # perder (timeout/rede) e o caixa clicar de novo, o backend
        # devolve a venda ja gravada em vez de vender duas vezes. So'
        # zera quando a venda deu certo ou o servidor RECUSOU de vez
        # (ver _ao_venda_sucesso).
        if self._chave_venda is None:
            self._chave_venda = uuid.uuid4().hex

        rodar_em_thread(
            self,
            enviar_venda,
            chave_idempotencia=self._chave_venda,
            itens=self.itens,
            forma_pagamento=tela.forma_pagamento,
            cliente_id=tela.cliente_id,
            desconto=desconto_liquido,
            observacao=tela.observacao.text().strip() or None,
            data_vencimento=None,
            forma_pagamento_2=tela.forma_pagamento_2,
            valor_forma_2=(
                tela.valor_forma_2 if tela.forma_pagamento_2 else None
            ),
            ao_sucesso=self._ao_venda_sucesso,
            ao_erro=self._ao_venda_erro,
            ao_finalizar=self._ao_venda_finalizada,
        )

    def _ao_venda_sucesso(self, response):

        tela = self._venda_pagamento_tela
        total = self._venda_total_em_andamento

        if response.status_code == 201:

            venda_criada = response.json()

            concluida = VendaConcluidaDialog(
                venda_criada["id"],
                total,
                self.itens,
                tela.forma_pagamento,
                cliente_nome=tela.cliente_nome,
                forma_pagamento_2=tela.forma_pagamento_2,
                valor_forma_2=tela.valor_forma_2,
                parent=self,
            )
            concluida.exec()

            self.limpar_venda()

        else:

            # o servidor respondeu e recusou (estoque, preco, caixa
            # fechado...): nada foi gravado, a proxima tentativa (talvez
            # com o carrinho corrigido) e' uma venda nova
            self._chave_venda = None

            try:
                erro = response.json()

                if isinstance(erro, dict):
                    erro = erro.get(
                        "detail",
                        str(erro)
                    )

            except Exception:
                erro = response.text

            QMessageBox.critical(
                self,
                "Erro",
                f"Erro ao finalizar a venda.\n\n{erro}"
            )

    def _ao_venda_erro(self, erro):

        # sem resposta do servidor (timeout, rede): a venda PODE ter
        # sido gravada. A chave continua a mesma, entao tentar de novo
        # e' seguro -- nao vende duas vezes.
        QMessageBox.critical(
            self,
            "Erro",
            f"{erro}\n\nSe a venda já tiver sido registrada, tentar de "
            "novo não vai duplicar."
        )

    def _ao_venda_finalizada(self):

        self._finalizando_venda = False
        self.bt_pagar.setEnabled(True)
        QApplication.restoreOverrideCursor()
        self._venda_pagamento_tela = None
        self._venda_total_em_andamento = None
