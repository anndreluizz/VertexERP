from io import BytesIO

import qrcode
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFrame,
    QLineEdit,
    QMessageBox,
    QScrollArea,
)

from design import tokens
from design.animations import fade_in
from design.icons import icone, icone_pixmap
from design.responsive import tamanho_fixo_seguro
from design.widgets import BotaoSecundario, BotaoSucesso, CampoTexto
from services.api import configuracoes
from services.pix_utils import montar_payload_pix
from services.worker import rodar_em_thread
from telas.selecionar_cliente import SelecionarClienteDialog
from utils.formatacao import formatar_moeda

# rotulo exibido, valor enviado pra API, icone (lucide) do botao
FORMAS = [
    ("Dinheiro", "DINHEIRO", "dollar-sign"),
    ("Débito", "DEBITO", "credit-card"),
    ("Crédito", "CREDITO", "credit-card"),
    ("PIX", "PIX", "refresh-cw"),
    ("Crediário", "PRAZO", "calendar"),
]

NOMES_FORMA = {valor: rotulo for rotulo, valor, _icone in FORMAS}

VALORES_RAPIDOS = [1, 2, 5, 10, 20, 50, 100]

# mesma paleta de monogramas ja usada em telas/pdv.py -- cor derivada
# do nome, pra sempre cair na mesma cor pro mesmo produto
_CORES_MONOGRAMA = [
    "#2563EB", "#16A34A", "#D97706", "#DB2777", "#7C3AED", "#0891B2",
]

# tolerancia de meio-centavo pra comparacao de valores em ponto flutuante
EPSILON = 0.005


def _texto_para_valor(texto):
    try:
        return float((texto or "").strip().replace(",", ".") or 0)
    except ValueError:
        return 0.0


def _fmt(valor):
    """Formata valores monetários no padrão da interface brasileira."""
    return formatar_moeda(valor, com_simbolo=False)


def _gerar_qrcode_pix_dados(valor):
    """Roda na worker thread -- busca a config PIX e gera a imagem do
    QR Code (CPU local, mas junto mesmo assim: sem motivo pra voltar
    na GUI thread so' pra chamar qrcode.make() logo depois)."""

    config = configuracoes()

    chave = (config.get("pix_chave") or "").strip()

    if not chave:
        return None, (
            "Cadastre uma chave PIX em Configurações "
            "para gerar o QR Code de cobrança."
        )

    nome = config.get("pix_nome") or config.get("nome_loja") or "LOJA"
    cidade = config.get("pix_cidade") or ""

    payload = montar_payload_pix(
        chave=chave,
        nome=nome,
        cidade=cidade,
        valor=valor,
    )

    imagem = qrcode.make(payload)

    buffer = BytesIO()
    imagem.save(buffer, format="PNG")

    texto_info = (
        f"Aponte a câmera do banco para pagar "
        f"R$ {_fmt(valor)} via PIX para {chave}"
    )

    return buffer.getvalue(), texto_info


class PagamentoWindow(QDialog):

    def __init__(
        self, total, itens=None, cliente_id=None, cliente_nome=None,
        desconto=0.0, acrescimo=0.0,
    ):

        super().__init__()

        self.total = total
        self.itens = itens or []
        self.subtotal = sum(item["preco"] * item["quantidade"] for item in self.itens)
        self.desconto = desconto or 0.0
        self.acrescimo = acrescimo or 0.0
        self.forma_pagamento = "DINHEIRO"
        self.recebido_acumulado = 0.0
        self.cliente_id = cliente_id
        self.cliente_nome = cliente_nome

        # pagamento dividido (opcional, no maximo 2 formas)
        self.dividir_pagamento = False
        self.forma_pagamento_2 = None
        self.valor_forma_2 = 0.0

        # guarda de reentrancia pros campos de valor 1/2, que se
        # atualizam um ao outro (preenchimento automatico do restante)
        self._sincronizando = False
        self._valor1_tocado = False
        self._valor2_tocado = False
        self._recebido_tocado = False

        self.setWindowTitle("Pagamento")
        tamanho_fixo_seguro(self, 1000, 780)
        self.setStyleSheet(f"background:{tokens.CARD};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        raiz.addWidget(self._construir_cabecalho())

        corpo = QHBoxLayout()
        corpo.setContentsMargins(0, 0, 0, 0)
        corpo.setSpacing(0)

        corpo.addWidget(self._construir_coluna_resumo())
        corpo.addWidget(self._construir_coluna_pagamento(), stretch=1)

        raiz.addLayout(corpo)

        raiz.addWidget(self._construir_barra_atalhos())

        # F2/F3 -- Esc ja funciona de graca (QDialog fecha com reject()
        # no Escape por padrao, sem precisar de nada extra aqui)
        self._atalho_cliente = QShortcut(QKeySequence("F2"), self)
        self._atalho_cliente.activated.connect(self.abrir_selecionar_cliente)

        self._atalho_confirmar = QShortcut(QKeySequence("F3"), self)
        self._atalho_confirmar.activated.connect(self.confirmar)

        self.selecionar_forma("DINHEIRO")

    def showEvent(self, event):
        super().showEvent(event)
        # Dinheiro e' a forma padrao -- o operador ja entra na tela
        # podendo digitar o valor recebido direto, sem precisar clicar
        # no campo primeiro.
        if self.forma_pagamento == "DINHEIRO":
            self.recebido.setFocus()
            self.recebido.selectAll()

    # ======================================
    # CONSTRUCAO DA UI
    # ======================================

    def _construir_cabecalho(self):

        cabecalho = QFrame()
        cabecalho.setStyleSheet(f"background:{tokens.SIDEBAR};")
        cabecalho.setFixedHeight(64)

        cab_layout = QHBoxLayout(cabecalho)
        cab_layout.setContentsMargins(24, 0, 24, 0)
        cab_layout.setSpacing(14)

        marca = QLabel("V")
        marca.setFixedSize(36, 36)
        marca.setAlignment(Qt.AlignCenter)
        marca.setStyleSheet(f"""
            background: {tokens.PRIMARIA};
            color: white;
            border-radius: {tokens.RADIUS_SM}px;
            font-size: 16px;
            font-weight: 800;
        """)
        cab_layout.addWidget(marca)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("Pagamento")
        titulo.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_CLARO}; "
            f"font-size:16px; font-weight:bold;"
        )

        subtitulo = QLabel("Selecione o método e finalize a venda")
        subtitulo.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_SIDEBAR_APAGADO}; "
            f"font-size:11px;"
        )

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        cab_layout.addLayout(col_titulo)
        cab_layout.addStretch()

        dica_esc = QLabel("Esc")
        dica_esc.setAlignment(Qt.AlignCenter)
        dica_esc.setStyleSheet(f"""
            background: {tokens.SIDEBAR_HOVER}; color:{tokens.TEXTO_SIDEBAR_APAGADO};
            border-radius: {tokens.RADIUS_SM}px; font-size: 11px; font-weight: 700;
            padding: 4px 10px;
        """)
        cab_layout.addWidget(dica_esc)

        self.bt_cancelar = QPushButton("✕  Cancelar Venda")
        self.bt_cancelar.setAutoDefault(False)
        self.bt_cancelar.setCursor(Qt.PointingHandCursor)
        self.bt_cancelar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.SIDEBAR_HOVER};
                color:{tokens.TEXTO_CLARO};
                border-radius:{tokens.RADIUS_SM}px;
                padding:8px 14px;
                font-weight:600;
            }}
            QPushButton:hover {{
                background:{tokens.ERRO};
            }}
        """)
        self.bt_cancelar.clicked.connect(self.reject)
        cab_layout.addWidget(self.bt_cancelar)

        return cabecalho

    def _construir_coluna_resumo(self):

        esquerda = QFrame()
        esquerda.setFixedWidth(340)
        esquerda.setStyleSheet(
            f"background:{tokens.FUNDO}; "
            f"border-right:1px solid {tokens.BORDA};"
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background:{tokens.FUNDO}; border:none;")

        conteudo = QFrame()
        conteudo.setStyleSheet(f"background:{tokens.FUNDO};")

        esq_layout = QVBoxLayout(conteudo)
        esq_layout.setContentsMargins(20, 20, 20, 16)
        esq_layout.setSpacing(4)

        cabecalho_resumo = QHBoxLayout()
        cabecalho_resumo.setSpacing(8)

        icone_resumo = QLabel()
        icone_resumo.setPixmap(icone_pixmap("shopping-cart", cor=tokens.TEXTO, tamanho=16))
        icone_resumo.setStyleSheet("background:transparent;")
        cabecalho_resumo.addWidget(icone_resumo)

        lbl_resumo_titulo = QLabel("Resumo da Venda")
        lbl_resumo_titulo.setStyleSheet(
            f"background:transparent; font-size:14px; "
            f"font-weight:800; color:{tokens.TEXTO};"
        )
        cabecalho_resumo.addWidget(lbl_resumo_titulo)
        cabecalho_resumo.addStretch()

        badge_itens = QLabel(f"{len(self.itens)} itens")
        badge_itens.setStyleSheet(f"""
            background:{tokens.CARD}; color:{tokens.TEXTO_SECUNDARIO};
            border-radius:{tokens.RADIUS_PILL}px;
            font-size:11px; font-weight:700; padding:3px 10px;
        """)
        cabecalho_resumo.addWidget(badge_itens)

        esq_layout.addLayout(cabecalho_resumo)
        esq_layout.addSpacing(12)

        for indice, item in enumerate(self.itens):
            esq_layout.addWidget(self._linha_item_resumo(item, indice))
            esq_layout.addSpacing(10)

        esq_layout.addSpacing(16)

        esq_layout.addLayout(self._linha_valor_resumo("Subtotal", self.subtotal))

        if self.desconto > EPSILON:
            esq_layout.addLayout(
                self._linha_valor_resumo("Desconto", -self.desconto, cor=tokens.ERRO)
            )

        if self.acrescimo > EPSILON:
            esq_layout.addLayout(
                self._linha_valor_resumo("Acréscimo", self.acrescimo, cor=tokens.SECUNDARIA)
            )

        esq_layout.addSpacing(10)

        caixa_total = QFrame()
        caixa_total.setStyleSheet(f"""
            QFrame {{
                background: {tokens.PRIMARIA_CLARA};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)
        layout_caixa_total = QVBoxLayout(caixa_total)
        layout_caixa_total.setContentsMargins(14, 10, 14, 10)
        layout_caixa_total.setSpacing(2)

        lbl_total_titulo = QLabel("TOTAL DA VENDA")
        lbl_total_titulo.setStyleSheet(
            f"background:transparent; font-size:11px; "
            f"font-weight:bold; color:{tokens.PRIMARIA_HOVER};"
        )
        layout_caixa_total.addWidget(lbl_total_titulo)

        self.lbl_total = QLabel(f"R$ {_fmt(self.total)}")
        self.lbl_total.setStyleSheet(
            f"background:transparent; font-size:30px; "
            f"font-weight:800; color:{tokens.PRIMARIA_HOVER};"
        )
        layout_caixa_total.addWidget(self.lbl_total)

        esq_layout.addWidget(caixa_total)
        esq_layout.addSpacing(14)

        esq_layout.addWidget(self._construir_linha_cliente())
        esq_layout.addSpacing(14)

        lbl_obs_titulo = QLabel("OBSERVAÇÃO (OPCIONAL)")
        lbl_obs_titulo.setStyleSheet(
            f"background:transparent; font-size:11px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO};"
        )
        esq_layout.addWidget(lbl_obs_titulo)
        esq_layout.addSpacing(4)

        self.observacao = CampoTexto(
            "Ex.: cliente pediu embalagem pra presente"
        )
        esq_layout.addWidget(self.observacao)

        esq_layout.addStretch()

        # ---- pago / restante -- discreto, o essencial ja esta' no
        # banner de status e nas 3 caixinhas do bloco de dinheiro; isso
        # aqui fica so' como registro compacto sempre visivel ----

        esq_layout.addSpacing(10)

        rodape_pago_restante = QHBoxLayout()

        col_pago = QVBoxLayout()
        col_pago.setSpacing(0)
        lbl_pago_titulo = QLabel("PAGO")
        lbl_pago_titulo.setStyleSheet(
            f"background:transparent; font-size:10px; "
            f"font-weight:bold; color:{tokens.TEXTO_TERCIARIO};"
        )
        self.lbl_pago = QLabel(f"R$ {_fmt(0)}")
        self.lbl_pago.setStyleSheet(
            f"background:transparent; font-size:13px; "
            f"font-weight:bold; color:{tokens.TEXTO};"
        )
        col_pago.addWidget(lbl_pago_titulo)
        col_pago.addWidget(self.lbl_pago)

        col_restante = QVBoxLayout()
        col_restante.setSpacing(0)
        lbl_restante_titulo = QLabel("RESTANTE")
        lbl_restante_titulo.setAlignment(Qt.AlignRight)
        lbl_restante_titulo.setStyleSheet(
            f"background:transparent; font-size:10px; "
            f"font-weight:bold; color:{tokens.TEXTO_TERCIARIO};"
        )
        self.lbl_restante = QLabel(f"R$ {_fmt(self.total)}")
        self.lbl_restante.setAlignment(Qt.AlignRight)
        self.lbl_restante.setStyleSheet(
            f"background:transparent; font-size:13px; "
            f"font-weight:800; color:{tokens.ALERTA};"
        )
        col_restante.addWidget(lbl_restante_titulo)
        col_restante.addWidget(self.lbl_restante)

        rodape_pago_restante.addLayout(col_pago)
        rodape_pago_restante.addStretch()
        rodape_pago_restante.addLayout(col_restante)

        esq_layout.addLayout(rodape_pago_restante)

        scroll.setWidget(conteudo)

        layout_externo = QVBoxLayout(esquerda)
        layout_externo.setContentsMargins(0, 0, 0, 0)
        layout_externo.addWidget(scroll)

        return esquerda

    def _linha_item_resumo(self, item, indice):

        linha = QFrame()
        linha.setStyleSheet("background:transparent; border:none;")

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        inicial = (item["nome"][:1] or "?").upper()
        cor = _CORES_MONOGRAMA[indice % len(_CORES_MONOGRAMA)]

        selo = QLabel(inicial)
        selo.setFixedSize(28, 28)
        selo.setAlignment(Qt.AlignCenter)
        selo.setStyleSheet(f"""
            background: {cor}; color: white; border-radius: 8px;
            font-size: 12px; font-weight: 800;
        """)
        layout.addWidget(selo)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(0)

        nome = QLabel(item["nome"])
        nome.setStyleSheet(
            f"background:transparent; font-size:12.5px; font-weight:700; color:{tokens.TEXTO};"
        )
        legenda = QLabel(f"{item['quantidade']} un × R$ {_fmt(item['preco'])}")
        legenda.setStyleSheet(
            f"background:transparent; font-size:11px; color:{tokens.TEXTO_TERCIARIO};"
        )
        col_texto.addWidget(nome)
        col_texto.addWidget(legenda)

        layout.addLayout(col_texto, 1)

        subtotal = item["preco"] * item["quantidade"]
        valor = QLabel(f"R$ {_fmt(subtotal)}")
        valor.setAlignment(Qt.AlignRight | Qt.AlignTop)
        valor.setStyleSheet(
            f"background:transparent; font-size:12.5px; font-weight:700; color:{tokens.TEXTO};"
        )
        layout.addWidget(valor)

        return linha

    def _linha_valor_resumo(self, rotulo, valor, cor=None):

        linha = QHBoxLayout()

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(
            f"background:transparent; font-size:12.5px; color:{tokens.TEXTO_SECUNDARIO};"
        )

        sinal = "- " if valor < 0 else ("+ " if cor and valor > 0 and rotulo != "Subtotal" else "")
        lbl_valor = QLabel(f"{sinal}R$ {_fmt(abs(valor))}")
        lbl_valor.setAlignment(Qt.AlignRight)
        lbl_valor.setStyleSheet(
            f"background:transparent; font-size:12.5px; font-weight:700; "
            f"color:{cor or tokens.TEXTO};"
        )

        linha.addWidget(lbl_rotulo)
        linha.addWidget(lbl_valor)

        return linha

    def _construir_linha_cliente(self):

        linha = QFrame()
        linha.setStyleSheet(f"""
            QFrame {{
                background: {tokens.CARD};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        icone_cliente = QLabel()
        icone_cliente.setPixmap(icone_pixmap("user", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        icone_cliente.setStyleSheet("background:transparent;")
        layout.addWidget(icone_cliente)

        col_cliente = QVBoxLayout()
        col_cliente.setSpacing(0)

        lbl_rotulo = QLabel("CLIENTE")
        lbl_rotulo.setStyleSheet(
            f"background:transparent; font-size:10px; "
            f"font-weight:bold; color:{tokens.TEXTO_TERCIARIO};"
        )
        col_cliente.addWidget(lbl_rotulo)

        self.lbl_cliente_selecionado = QLabel(
            self.cliente_nome or "Não informado"
        )
        self.lbl_cliente_selecionado.setWordWrap(True)
        self.lbl_cliente_selecionado.setStyleSheet(f"""
            background:transparent; font-size:13px; font-weight:700;
            color: {tokens.SECUNDARIA if self.cliente_nome else tokens.TEXTO_SECUNDARIO};
        """)
        col_cliente.addWidget(self.lbl_cliente_selecionado)

        layout.addLayout(col_cliente, 1)

        self.bt_selecionar_cliente = QPushButton("Selecionar (F2)")
        self.bt_selecionar_cliente.setCursor(Qt.PointingHandCursor)
        self.bt_selecionar_cliente.setAutoDefault(False)
        self.bt_selecionar_cliente.setStyleSheet(f"""
            QPushButton {{
                background:transparent; border:none;
                color:{tokens.PRIMARIA}; font-size:12px; font-weight:700;
            }}
            QPushButton:hover {{ color:{tokens.PRIMARIA_HOVER}; }}
        """)
        self.bt_selecionar_cliente.clicked.connect(self.abrir_selecionar_cliente)
        layout.addWidget(self.bt_selecionar_cliente)

        return linha

    def _construir_coluna_pagamento(self):
        """Coluna direita = area rolavel com a selecao de forma(s) +
        campos, e um rodape fixo (status + CONFIRMAR VENDA) que nunca
        sai de vista — mesmo com o pagamento dividido aberto e o bloco
        de dinheiro/troco visiveis ao mesmo tempo, o botao de ação
        continua sempre alcançável, sem precisar redimensionar a
        janela."""

        direita = QFrame()
        direita.setStyleSheet(f"background:{tokens.CARD};")

        dir_layout = QVBoxLayout(direita)
        dir_layout.setContentsMargins(0, 0, 0, 0)
        dir_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(f"background:{tokens.CARD}; border:none;")

        conteudo = QFrame()
        conteudo.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(conteudo)
        layout.setContentsMargins(24, 24, 24, 8)
        layout.setSpacing(16)

        layout.addLayout(self._titulo_passo("1", "Forma de pagamento"))

        self.lbl_forma_titulo = QLabel("")
        self.lbl_forma_titulo.setVisible(False)
        layout.addWidget(self.lbl_forma_titulo)

        formas_layout = QHBoxLayout()
        formas_layout.setSpacing(10)

        self.botoes_forma = {}

        for rotulo, valor, _icone_nome in FORMAS:

            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setAutoDefault(False)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setMinimumHeight(68)
            bt.setIconSize(QSize(18, 18))
            bt.clicked.connect(
                lambda checked, v=valor: self.selecionar_forma(v)
            )

            self.botoes_forma[valor] = bt
            formas_layout.addWidget(bt)

        layout.addLayout(formas_layout)

        # ---- dividir pagamento (2ª forma) ----

        self.bt_dividir = BotaoSecundario(
            "DIVIDIR PAGAMENTO", icone_nome="plus"
        )
        self.bt_dividir.setAutoDefault(False)
        self.bt_dividir.setMinimumHeight(40)
        self.bt_dividir.clicked.connect(self.ativar_divisao)
        layout.addWidget(self.bt_dividir)

        self.bloco_divisao = self._construir_bloco_divisao()
        self.bloco_divisao.setVisible(False)
        layout.addWidget(self.bloco_divisao)

        layout.addLayout(self._titulo_passo("2", "Detalhes do pagamento"))

        # ---- entrada de valor (dinheiro / troco) ----

        self.bloco_dinheiro = self._construir_bloco_dinheiro()
        layout.addWidget(self.bloco_dinheiro)

        # ---- QR Code (pix) ----

        self.bloco_pix = self._construir_bloco_pix()
        layout.addWidget(self.bloco_pix)

        self.gerar_qrcode_pix()

        layout.addStretch()

        scroll.setWidget(conteudo)
        dir_layout.addWidget(scroll, stretch=1)

        # ---- rodape fixo: status do pagamento + confirmar ----

        rodape = QFrame()
        rodape.setStyleSheet(
            f"background:{tokens.CARD}; "
            f"border-top:1px solid {tokens.BORDA};"
        )

        rodape_layout = QVBoxLayout(rodape)
        rodape_layout.setContentsMargins(24, 16, 24, 20)
        rodape_layout.setSpacing(10)

        self.banner_status = self._construir_banner_status()
        rodape_layout.addWidget(self.banner_status)

        self.lbl_hint_confirmar = QLabel("")
        self.lbl_hint_confirmar.setAlignment(Qt.AlignCenter)
        self.lbl_hint_confirmar.setWordWrap(True)
        self.lbl_hint_confirmar.setStyleSheet(
            f"background:transparent; font-size:12px; "
            f"font-weight:600; color:{tokens.ERRO};"
        )
        self.lbl_hint_confirmar.setVisible(False)
        rodape_layout.addWidget(self.lbl_hint_confirmar)

        self.bt_confirmar = BotaoSucesso("CONFIRMAR VENDA (F3)", icone_nome="check")
        self.bt_confirmar.setMinimumHeight(52)
        self.bt_confirmar.setAutoDefault(True)
        self.bt_confirmar.setDefault(True)
        self.bt_confirmar.clicked.connect(self.confirmar)

        rodape_layout.addWidget(self.bt_confirmar)

        dir_layout.addWidget(rodape)

        return direita

    def _titulo_passo(self, numero, texto):

        linha = QHBoxLayout()
        linha.setSpacing(8)

        selo = QLabel(numero)
        selo.setFixedSize(22, 22)
        selo.setAlignment(Qt.AlignCenter)
        selo.setStyleSheet(f"""
            background: {tokens.PRIMARIA}; color: white;
            border-radius: 11px; font-size: 12px; font-weight: 800;
        """)
        linha.addWidget(selo)

        lbl = QLabel(texto)
        lbl.setStyleSheet(
            f"background:transparent; font-size:14px; "
            f"font-weight:800; color:{tokens.TEXTO};"
        )
        linha.addWidget(lbl)
        linha.addStretch()

        return linha

    def _construir_bloco_divisao(self):

        bloco = QFrame()
        bloco.setObjectName("blocoDivisao")
        bloco.setStyleSheet(f"""
            QFrame#blocoDivisao {{
                background: {tokens.PRIMARIA_CLARA};
                border-radius: {tokens.RADIUS_MD}px;
            }}
        """)

        layout = QVBoxLayout(bloco)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        cabecalho = QHBoxLayout()

        lbl_titulo = QLabel("🔀  PAGAMENTO DIVIDIDO EM 2 FORMAS")
        lbl_titulo.setStyleSheet(
            f"background:transparent; font-size:12px; "
            f"font-weight:800; color:{tokens.PRIMARIA_HOVER};"
        )

        self.bt_remover_divisao = QPushButton("✕  Remover")
        self.bt_remover_divisao.setAutoDefault(False)
        self.bt_remover_divisao.setCursor(Qt.PointingHandCursor)
        self.bt_remover_divisao.setStyleSheet(f"""
            QPushButton {{
                background:transparent;
                color:{tokens.ERRO};
                font-weight:700;
                font-size:12px;
                border:none;
                padding:4px 6px;
            }}
            QPushButton:hover {{
                color:{tokens.ERRO_HOVER};
                text-decoration:underline;
            }}
        """)
        self.bt_remover_divisao.clicked.connect(self.remover_divisao)

        cabecalho.addWidget(lbl_titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(self.bt_remover_divisao)

        layout.addLayout(cabecalho)

        # ---- valor da 1ª forma ----

        self.lbl_caption_valor_1 = QLabel("VALOR NA 1ª FORMA")
        self.lbl_caption_valor_1.setStyleSheet(
            f"background:transparent; font-size:10px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO};"
        )
        layout.addWidget(self.lbl_caption_valor_1)

        self.campo_valor_1 = self._criar_campo_valor()
        self.campo_valor_1.textEdited.connect(self._valor1_editado)
        layout.addWidget(self.campo_valor_1)

        # ---- seletor + valor da 2ª forma ----

        lbl_2forma_titulo = QLabel("2ª FORMA DE PAGAMENTO")
        lbl_2forma_titulo.setStyleSheet(
            f"background:transparent; font-size:10px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO}; "
            f"margin-top:6px;"
        )
        layout.addWidget(lbl_2forma_titulo)

        formas_2_layout = QHBoxLayout()
        formas_2_layout.setSpacing(6)

        self.botoes_forma_2 = {}

        for rotulo, valor, _icone_nome in FORMAS:

            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setMinimumHeight(40)
            bt.setAutoDefault(False)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setIconSize(QSize(16, 16))
            bt.clicked.connect(
                lambda checked, v=valor: self.selecionar_forma_2(v)
            )

            self.botoes_forma_2[valor] = bt
            formas_2_layout.addWidget(bt)

        layout.addLayout(formas_2_layout)

        self.lbl_caption_valor_2 = QLabel("VALOR NA 2ª FORMA")
        self.lbl_caption_valor_2.setStyleSheet(
            f"background:transparent; font-size:10px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO};"
        )
        layout.addWidget(self.lbl_caption_valor_2)

        self.campo_valor_2 = self._criar_campo_valor()
        self.campo_valor_2.textEdited.connect(self._valor2_editado)
        layout.addWidget(self.campo_valor_2)

        return bloco

    @staticmethod
    def _criar_campo_valor():

        campo = QLineEdit()
        campo.setPlaceholderText("0,00")
        campo.setAlignment(Qt.AlignRight)
        campo.setStyleSheet(f"""
            QLineEdit {{
                background:{tokens.FUNDO};
                font-size:22px;
                font-weight:800;
                color:{tokens.TEXTO};
                border-radius:{tokens.RADIUS_SM}px;
                padding:6px 12px;
            }}
            QLineEdit:focus {{
                background:{tokens.PRIMARIA_CLARA};
            }}
        """)

        return campo

    def _construir_bloco_dinheiro(self):

        bloco = QFrame()

        bloco_layout = QVBoxLayout(bloco)
        bloco_layout.setContentsMargins(0, 0, 0, 0)
        bloco_layout.setSpacing(14)

        lbl_entrada_titulo = QLabel("DINHEIRO RECEBIDO DO CLIENTE")
        lbl_entrada_titulo.setStyleSheet(
            f"background:transparent; font-size:11px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO};"
        )
        bloco_layout.addWidget(lbl_entrada_titulo)

        linha_entrada = QHBoxLayout()
        linha_entrada.setSpacing(14)

        caixa_recebido = QFrame()
        caixa_recebido.setStyleSheet(f"""
            QFrame {{
                background: {tokens.FUNDO};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)
        layout_caixa_recebido = QHBoxLayout(caixa_recebido)
        layout_caixa_recebido.setContentsMargins(14, 4, 14, 4)

        lbl_prefixo = QLabel("R$")
        lbl_prefixo.setStyleSheet(
            f"background:transparent; font-size:20px; font-weight:700; "
            f"color:{tokens.TEXTO_TERCIARIO};"
        )
        layout_caixa_recebido.addWidget(lbl_prefixo)

        self.recebido = QLineEdit()
        self.recebido.setPlaceholderText("0,00")
        self.recebido.setAlignment(Qt.AlignRight)
        self.recebido.setStyleSheet(f"""
            QLineEdit {{
                background:transparent;
                font-size:28px;
                font-weight:800;
                color:{tokens.TEXTO};
                border:none;
                padding:8px 0;
            }}
        """)
        self.recebido.textEdited.connect(self._recebido_editado)
        layout_caixa_recebido.addWidget(self.recebido)

        linha_entrada.addWidget(caixa_recebido, 1)

        grade_valores = QGridLayout()
        grade_valores.setSpacing(6)

        botoes_rapidos = [(f"R$ {v}", v) for v in VALORES_RAPIDOS[2:]]

        for indice, (rotulo, valor) in enumerate(botoes_rapidos):

            bt = QPushButton(rotulo)
            bt.setAutoDefault(False)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setMinimumHeight(30)
            bt.setStyleSheet(f"""
                QPushButton {{
                    background:{tokens.FUNDO};
                    color:{tokens.TEXTO};
                    border-radius:{tokens.RADIUS_SM}px;
                    font-weight:600;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background:{tokens.BORDA};
                }}
            """)
            bt.clicked.connect(
                lambda checked, v=valor: self.adicionar_valor(v)
            )

            grade_valores.addWidget(bt, indice // 3, indice % 3)

        bt_exato = QPushButton("Valor exato")
        bt_exato.setAutoDefault(False)
        bt_exato.setCursor(Qt.PointingHandCursor)
        bt_exato.setMinimumHeight(30)
        bt_exato.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.PRIMARIA_CLARA};
                color:{tokens.PRIMARIA_HOVER};
                border-radius:{tokens.RADIUS_SM}px;
                font-weight:700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background:{tokens.PRIMARIA};
                color: white;
            }}
        """)
        bt_exato.clicked.connect(self.definir_valor_exato)

        posicao = len(botoes_rapidos)
        grade_valores.addWidget(bt_exato, posicao // 3, posicao % 3)

        linha_entrada.addLayout(grade_valores, 1)

        bloco_layout.addLayout(linha_entrada)

        # ---- 3 caixinhas: total da venda / valor recebido / troco ----

        linha_caixinhas = QHBoxLayout()
        linha_caixinhas.setSpacing(10)

        self.lbl_recebido_resumo = QLabel(f"R$ {_fmt(0)}")
        self.troco = QLabel(f"R$ {_fmt(0)}")

        linha_caixinhas.addWidget(
            self._caixinha_resumo("dollar-sign", "Total da venda", f"R$ {_fmt(self.total)}")
        )
        linha_caixinhas.addWidget(
            self._caixinha_resumo("wallet", "Valor recebido", None, self.lbl_recebido_resumo)
        )
        linha_caixinhas.addWidget(
            self._caixinha_resumo("refresh-cw", "Troco", None, self.troco)
        )

        bloco_layout.addLayout(linha_caixinhas)

        return bloco

    def _caixinha_resumo(self, icone_nome, rotulo, texto_fixo=None, lbl_valor=None):

        caixa = QFrame()
        caixa.setStyleSheet(f"""
            QFrame {{
                background: {tokens.FUNDO};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

        layout = QVBoxLayout(caixa)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        topo = QHBoxLayout()
        topo.setSpacing(6)

        lbl_icone = QLabel()
        lbl_icone.setPixmap(icone_pixmap(icone_nome, cor=tokens.TEXTO_TERCIARIO, tamanho=13))
        lbl_icone.setStyleSheet("background:transparent;")
        topo.addWidget(lbl_icone)

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(
            f"background:transparent; font-size:11px; color:{tokens.TEXTO_SECUNDARIO};"
        )
        topo.addWidget(lbl_rotulo)
        topo.addStretch()

        layout.addLayout(topo)

        if lbl_valor is None:
            lbl_valor = QLabel(texto_fixo or "")

        lbl_valor.setStyleSheet(
            f"background:transparent; font-size:15px; font-weight:800; color:{tokens.TEXTO};"
        )
        layout.addWidget(lbl_valor)

        return caixa

    def _construir_bloco_pix(self):

        bloco = QFrame()

        pix_layout = QVBoxLayout(bloco)
        pix_layout.setContentsMargins(0, 0, 0, 0)
        pix_layout.setSpacing(10)
        pix_layout.setAlignment(Qt.AlignHCenter)

        self.lbl_qrcode = QLabel()
        self.lbl_qrcode.setAlignment(Qt.AlignCenter)
        self.lbl_qrcode.setFixedSize(200, 200)
        self.lbl_qrcode.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO}; font-size:12px;"
        )

        self.lbl_pix_info = QLabel()
        self.lbl_pix_info.setAlignment(Qt.AlignCenter)
        self.lbl_pix_info.setWordWrap(True)
        self.lbl_pix_info.setStyleSheet(
            f"background:transparent; font-size:11px; color:{tokens.TEXTO_SECUNDARIO};"
        )

        pix_layout.addWidget(self.lbl_qrcode, alignment=Qt.AlignHCenter)
        pix_layout.addWidget(self.lbl_pix_info)

        return bloco

    def _construir_banner_status(self):

        banner = QFrame()
        banner.setObjectName("bannerStatus")
        banner.setMinimumHeight(56)

        layout = QVBoxLayout(banner)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(2)

        self.lbl_status_rotulo = QLabel("")
        self.lbl_status_rotulo.setStyleSheet(
            "background:transparent; font-size:11px; font-weight:800;"
        )

        self.lbl_status_valor = QLabel("")
        self.lbl_status_valor.setStyleSheet(
            "background:transparent; font-size:22px; font-weight:800;"
        )

        layout.addWidget(self.lbl_status_rotulo)
        layout.addWidget(self.lbl_status_valor)

        return banner

    def _construir_barra_atalhos(self):

        barra = QFrame()
        barra.setFixedHeight(38)
        barra.setStyleSheet(f"""
            QFrame {{
                background: {tokens.FUNDO};
                border-top: 1px solid {tokens.BORDA};
            }}
        """)

        layout = QHBoxLayout(barra)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(20)

        for tecla, rotulo in (("F3", "Confirmar"), ("F2", "Cliente"), ("Esc", "Cancelar")):
            layout.addLayout(self._item_atalho(tecla, rotulo))

        layout.addStretch()

        self.lbl_loja = QLabel("")
        self.lbl_loja.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_SECUNDARIO}; font-size:11px;"
        )
        layout.addWidget(self.lbl_loja)

        rodar_em_thread(
            self,
            configuracoes,
            ao_sucesso=self._ao_config_rodape_sucesso,
        )

        return barra

    def _ao_config_rodape_sucesso(self, config):
        self.lbl_loja.setText(config.get("nome_loja") or "Vertex ERP")

    def _item_atalho(self, tecla, rotulo):

        item = QHBoxLayout()
        item.setSpacing(6)

        badge_tecla = QLabel(tecla)
        badge_tecla.setAlignment(Qt.AlignCenter)
        badge_tecla.setFixedHeight(18)
        badge_tecla.setStyleSheet(f"""
            background:{tokens.CARD}; color:{tokens.TEXTO_SECUNDARIO};
            border:1px solid {tokens.BORDA}; border-radius:4px;
            font-size:10px; font-weight:700; padding: 0 6px;
        """)

        lbl_rotulo = QLabel(rotulo)
        lbl_rotulo.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; font-size:11px;"
        )

        item.addWidget(badge_tecla)
        item.addWidget(lbl_rotulo)

        return item

    # ======================================
    # SELECAO DE FORMA (1ª / 2ª)
    # ======================================

    def selecionar_forma(self, valor):

        self.forma_pagamento = valor

        for rotulo, chave, icone_nome in FORMAS:

            botao = self.botoes_forma[chave]
            selecionado = chave == valor

            botao.setChecked(selecionado)
            self._pintar_pill(botao, icone_nome, selecionado)

        self._atualizar_visibilidade_blocos()

        if valor == "PRAZO" and self.cliente_id is None:
            self.abrir_selecionar_cliente()

        # a 2ª forma nao pode repetir a principal
        for chave, botao in self.botoes_forma_2.items():
            botao.setEnabled(chave != valor)

        if self.forma_pagamento_2 == valor:
            self.selecionar_forma_2(None)

        self._recalcular_resumo()

    def selecionar_forma_2(self, valor):

        self.forma_pagamento_2 = valor

        for rotulo, chave, icone_nome in FORMAS:

            botao = self.botoes_forma_2[chave]
            selecionado = chave == valor

            botao.setChecked(selecionado)
            self._pintar_pill(botao, icone_nome, selecionado, pequeno=True)

        self.lbl_caption_valor_2.setText(
            f"VALOR NA 2ª FORMA — {NOMES_FORMA[valor].upper()}" if valor
            else "VALOR NA 2ª FORMA"
        )

        if valor is None:
            self._sincronizando = True
            self.campo_valor_2.setText("")
            self._sincronizando = False
            self._valor2_tocado = False

        self._atualizar_visibilidade_blocos()

        if valor == "PRAZO" and self.cliente_id is None:
            self.abrir_selecionar_cliente()

        self._recalcular_resumo()

    def _pintar_pill(self, botao, icone_nome, selecionado, pequeno=False):

        cor_fundo = tokens.PRIMARIA if selecionado else tokens.CARD
        cor_texto = tokens.TEXTO_CLARO if selecionado else tokens.TEXTO
        cor_borda = tokens.PRIMARIA if selecionado else tokens.BORDA

        botao.setIcon(icone(icone_nome, cor=cor_texto, tamanho=16 if pequeno else 18))

        botao.setStyleSheet(f"""
            QPushButton {{
                background: {cor_fundo};
                color: {cor_texto};
                border: 1.5px solid {cor_borda};
                border-radius: {tokens.RADIUS_SM}px;
                font-weight: 700;
                font-size: {11 if pequeno else 13}px;
                padding: 4px 6px;
            }}
            QPushButton:hover {{
                border-color: {tokens.PRIMARIA};
            }}
            QPushButton:disabled {{
                background: {tokens.FUNDO};
                color: {tokens.TEXTO_TERCIARIO};
                border-color: {tokens.BORDA};
            }}
        """)

    def _atualizar_visibilidade_blocos(self):

        forma_2 = self.forma_pagamento_2 if self.dividir_pagamento else None

        self.bloco_dinheiro.setVisible(
            self.forma_pagamento == "DINHEIRO" or forma_2 == "DINHEIRO"
        )
        self.bloco_pix.setVisible(self.forma_pagamento == "PIX")

    # ======================================
    # DIVIDIR PAGAMENTO
    # ======================================

    def ativar_divisao(self):

        self.dividir_pagamento = True

        self.bt_dividir.setVisible(False)
        self.bloco_divisao.setVisible(True)
        fade_in(self.bloco_divisao)

        self.lbl_caption_valor_1.setText(
            f"VALOR NA 1ª FORMA — {NOMES_FORMA[self.forma_pagamento].upper()}"
        )

        self._valor1_tocado = False
        self._valor2_tocado = False
        self._recebido_tocado = False

        self._sincronizando = True
        self.campo_valor_1.setText("")
        self.campo_valor_2.setText("")
        self._sincronizando = False

        self.recebido.setText("")

        self._atualizar_visibilidade_blocos()
        self._recalcular_resumo()

    def remover_divisao(self):

        self.dividir_pagamento = False

        self.bt_dividir.setVisible(True)
        self.bloco_divisao.setVisible(False)

        self.selecionar_forma_2(None)

        self.valor_forma_2 = 0.0

        self._atualizar_visibilidade_blocos()
        self._recalcular_resumo()

    def _valor1_editado(self, texto):

        if self._sincronizando:
            return

        self._valor1_tocado = True
        valor_1 = _texto_para_valor(texto)

        if not self._valor2_tocado:
            resto = max(0.0, self.total - valor_1)
            self._sincronizando = True
            self.campo_valor_2.setText(_fmt(resto))
            self._sincronizando = False

        self._recalcular_resumo()

    def _valor2_editado(self, texto):

        if self._sincronizando:
            return

        self._valor2_tocado = True
        valor_2 = _texto_para_valor(texto)

        if not self._valor1_tocado:
            resto = max(0.0, self.total - valor_2)
            self._sincronizando = True
            self.campo_valor_1.setText(_fmt(resto))
            self._sincronizando = False

        self._recalcular_resumo()

    def _recebido_editado(self, texto):

        self._recebido_tocado = True
        self._recalcular_resumo()

    # ======================================
    # CALCULOS / RESUMO EM TEMPO REAL
    # ======================================

    def valor_principal(self):
        """Quanto da venda fica coberto pela forma de pagamento
        principal — o total inteiro, ou o que foi digitado na 1ª forma
        quando o pagamento foi dividido."""

        if not self.dividir_pagamento:
            return self.total

        return _texto_para_valor(self.campo_valor_1.text())

    def _valor_dinheiro_necessario(self):
        """Quanto em dinheiro precisa ser recebido pra cobrir a parte
        da venda atribuida a essa forma — considera dinheiro tanto na
        1ª quanto na 2ª forma."""

        if self.forma_pagamento == "DINHEIRO":
            return self.valor_principal()

        if self.dividir_pagamento and self.forma_pagamento_2 == "DINHEIRO":
            return _texto_para_valor(self.campo_valor_2.text())

        return None

    def _recalcular_resumo(self):

        if self.dividir_pagamento:

            valor_1 = _texto_para_valor(self.campo_valor_1.text())
            valor_2 = _texto_para_valor(self.campo_valor_2.text())

            self.valor_forma_2 = valor_2
            pago = valor_1 + valor_2

        elif self.forma_pagamento == "DINHEIRO":

            recebido = _texto_para_valor(self.recebido.text())
            pago = min(recebido, self.total)
            self.valor_forma_2 = 0.0

        else:

            pago = self.total
            self.valor_forma_2 = 0.0

        restante = self.total - pago

        # no pagamento dividido, o campo "dinheiro recebido" comeca
        # espelhando o valor atribuido a forma em dinheiro (o caso mais
        # comum é o cliente entregar o valor exato) — o operador so
        # precisa mexer nele se receber mais, pra calcular o troco
        if self.dividir_pagamento and not self._recebido_tocado:

            necessario = self._valor_dinheiro_necessario()

            if necessario is not None:
                self.recebido.setText(_fmt(necessario))

        self.lbl_pago.setText(f"R$ {_fmt(max(0.0, pago))}")
        self.lbl_restante.setText(f"R$ {_fmt(max(0.0, restante))}")

        if restante > EPSILON:
            self.lbl_restante.setStyleSheet(
                f"background:transparent; font-size:13px; "
                f"font-weight:800; color:{tokens.ALERTA};"
            )
        else:
            self.lbl_restante.setStyleSheet(
                f"background:transparent; font-size:13px; "
                f"font-weight:800; color:{tokens.SECUNDARIA};"
            )

        self._atualizar_banner_status(restante)
        self.calcular_troco()

        if self.forma_pagamento == "PIX":
            self.gerar_qrcode_pix()

        self._atualizar_estado_confirmar()

    def _atualizar_banner_status(self, restante):

        if restante < -EPSILON:

            self.banner_status.setStyleSheet(f"""
                QFrame#bannerStatus {{
                    background:{tokens.ERRO_CLARO};
                    border-radius:{tokens.RADIUS_MD}px;
                }}
            """)
            self.lbl_status_rotulo.setStyleSheet(
                f"background:transparent; font-size:11px; "
                f"font-weight:800; color:{tokens.ERRO_HOVER};"
            )
            self.lbl_status_rotulo.setText("⚠ EXCESSO — AJUSTE OS VALORES")
            self.lbl_status_valor.setStyleSheet(
                f"background:transparent; font-size:22px; "
                f"font-weight:800; color:{tokens.ERRO_HOVER};"
            )
            self.lbl_status_valor.setText(f"R$ {_fmt(-restante)} a mais")

        elif restante > EPSILON:

            self.banner_status.setStyleSheet(f"""
                QFrame#bannerStatus {{
                    background:{tokens.ALERTA_CLARO};
                    border-radius:{tokens.RADIUS_MD}px;
                }}
            """)
            self.lbl_status_rotulo.setStyleSheet(
                "background:transparent; font-size:11px; "
                f"font-weight:800; color:{tokens.ALERTA_TEXTO};"
            )
            self.lbl_status_rotulo.setText("FALTA RECEBER")
            self.lbl_status_valor.setStyleSheet(
                "background:transparent; font-size:22px; "
                f"font-weight:800; color:{tokens.ALERTA_TEXTO};"
            )
            self.lbl_status_valor.setText(f"R$ {_fmt(restante)}")

        else:

            self.banner_status.setStyleSheet(f"""
                QFrame#bannerStatus {{
                    background:{tokens.SUCESSO_CLARO};
                    border-radius:{tokens.RADIUS_MD}px;
                }}
            """)
            self.lbl_status_rotulo.setStyleSheet(
                f"background:transparent; font-size:11px; "
                f"font-weight:800; color:{tokens.SECUNDARIA_HOVER};"
            )
            self.lbl_status_rotulo.setText("🟢 PAGAMENTO COMPLETO")
            self.lbl_status_valor.setStyleSheet(
                f"background:transparent; font-size:22px; "
                f"font-weight:800; color:{tokens.SECUNDARIA_HOVER};"
            )
            self.lbl_status_valor.setText(f"R$ {_fmt(self.total)}")

    def _atualizar_estado_confirmar(self):

        valido, motivo = self._pagamento_valido()

        self.bt_confirmar.setEnabled(valido)
        self.lbl_hint_confirmar.setVisible(not valido)

        if not valido:
            self.lbl_hint_confirmar.setText(motivo)

    def _pagamento_valido(self):

        formas_da_venda = [self.forma_pagamento]
        if self.dividir_pagamento and self.forma_pagamento_2:
            formas_da_venda.append(self.forma_pagamento_2)

        if self.dividir_pagamento:

            if not self.forma_pagamento_2:
                return False, "Escolha a 2ª forma de pagamento."

            valor_1 = _texto_para_valor(self.campo_valor_1.text())
            valor_2 = _texto_para_valor(self.campo_valor_2.text())

            if valor_2 <= EPSILON:
                return False, "Informe o valor da 2ª forma de pagamento."

            if valor_1 <= EPSILON:
                return False, "O valor da 1ª forma precisa ser maior que zero."

            diferenca = (valor_1 + valor_2) - self.total

            if diferenca > EPSILON:
                return False, (
                    f"O valor informado ultrapassa o total em "
                    f"R$ {_fmt(diferenca)}. Ajuste os valores."
                )

            if diferenca < -EPSILON:
                return False, (
                    f"Ainda falta R$ {_fmt(-diferenca)} pra completar "
                    f"o pagamento."
                )

        necessario_dinheiro = self._valor_dinheiro_necessario()

        if necessario_dinheiro is not None:

            recebido = _texto_para_valor(self.recebido.text())

            if recebido + EPSILON < necessario_dinheiro:
                return False, "Informe o valor recebido em dinheiro."

        if "PRAZO" in formas_da_venda and self.cliente_id is None:
            return False, "Selecione o cliente do crediário."

        return True, None

    def calcular_troco(self):

        necessario = self._valor_dinheiro_necessario()

        if necessario is None:
            self.troco.setText(f"R$ {_fmt(0)}")
            self.lbl_recebido_resumo.setText(f"R$ {_fmt(0)}")
            return

        recebido = _texto_para_valor(self.recebido.text())

        troco = max(0.0, recebido - necessario)

        cor = tokens.SECUNDARIA if troco > EPSILON else tokens.TEXTO
        self.troco.setStyleSheet(
            f"background:transparent; font-size:15px; "
            f"font-weight:800; color:{cor};"
        )
        self.troco.setText(f"R$ {_fmt(troco)}")
        self.lbl_recebido_resumo.setText(f"R$ {_fmt(recebido)}")

    # ======================================
    # CLIENTE / PIX
    # ======================================

    def abrir_selecionar_cliente(self):

        dialogo = SelecionarClienteDialog(self)
        dialogo.cliente_selecionado.connect(self.definir_cliente)
        dialogo.exec()

    def definir_cliente(self, cliente):

        self.cliente_id = cliente["id"]
        self.cliente_nome = cliente["nome"]

        self.lbl_cliente_selecionado.setText(cliente["nome"])
        self.lbl_cliente_selecionado.setStyleSheet(
            f"background:transparent; font-size:13px; "
            f"font-weight:700; color:{tokens.SECUNDARIA};"
        )

        self._atualizar_estado_confirmar()

    def gerar_qrcode_pix(self):

        self.lbl_qrcode.setText("Gerando QR Code...")
        self.lbl_pix_info.setText("")

        rodar_em_thread(
            self,
            _gerar_qrcode_pix_dados,
            self.valor_principal(),
            ao_sucesso=self._ao_qrcode_pix_sucesso,
            ao_erro=self._ao_qrcode_pix_erro,
        )

    def _ao_qrcode_pix_sucesso(self, resultado):

        png_bytes, texto_info = resultado

        if png_bytes is None:
            self.lbl_qrcode.setText("QR Code indisponível")
            self.lbl_pix_info.setText(texto_info)
            return

        pixmap = QPixmap()
        pixmap.loadFromData(png_bytes)

        self.lbl_qrcode.setPixmap(
            pixmap.scaled(
                200,
                200,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

        self.lbl_pix_info.setText(texto_info)

    def _ao_qrcode_pix_erro(self, erro):
        self.lbl_qrcode.setText("QR Code indisponível")
        self.lbl_pix_info.setText(f"Não foi possível gerar o QR Code.\n{erro}")

    def adicionar_valor(self, valor):

        self.recebido_acumulado += valor

        self.recebido.setText(_fmt(self.recebido_acumulado))
        self._recalcular_resumo()

    def definir_valor_exato(self):
        """Preenche o campo com exatamente o que falta receber em
        dinheiro -- o caso mais comum quando o cliente já entrega o
        valor certo, sem precisar calcular troco."""

        necessario = self._valor_dinheiro_necessario()
        valor = necessario if necessario is not None else self.total

        self.recebido_acumulado = valor
        self.recebido.setText(_fmt(valor))
        self._recalcular_resumo()

    # ======================================
    # CONFIRMACAO
    # ======================================

    def confirmar(self):

        valido, motivo = self._pagamento_valido()

        if not valido:
            QMessageBox.warning(self, "Atenção", motivo)
            return

        if not self.dividir_pagamento:
            self.forma_pagamento_2 = None
            self.valor_forma_2 = 0.0

        self.accept()
