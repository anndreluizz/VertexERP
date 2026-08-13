from io import BytesIO

import qrcode
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
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
from design.icons import icone
from design.responsive import tamanho_fixo_seguro
from design.widgets import BotaoSecundario, BotaoSucesso, CampoTexto
from services.api import configuracoes
from services.pix_utils import montar_payload_pix
from telas.selecionar_cliente import SelecionarClienteDialog

# rotulo exibido, valor enviado pra API, icone (lucide) do botao
FORMAS = [
    ("Dinheiro", "DINHEIRO", "dollar-sign"),
    ("Débito", "DEBITO", "credit-card"),
    ("Crédito", "CREDITO", "credit-card"),
    ("PIX", "PIX", "refresh-cw"),
    ("A Prazo", "PRAZO", "calendar"),
]

NOMES_FORMA = {valor: rotulo for rotulo, valor, _icone in FORMAS}

VALORES_RAPIDOS = [1, 2, 5, 10, 20, 50, 100]

# tolerancia de meio-centavo pra comparacao de valores em ponto flutuante
EPSILON = 0.005


def _texto_para_valor(texto):
    try:
        return float((texto or "").strip().replace(",", ".") or 0)
    except ValueError:
        return 0.0


def _fmt(valor):
    return f"{valor:.2f}"


class PagamentoWindow(QDialog):

    def __init__(self, total, itens=None, cliente_id=None, cliente_nome=None):

        super().__init__()

        self.total = total
        self.itens = itens or []
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

        self.selecionar_forma("DINHEIRO")

    # ======================================
    # CONSTRUCAO DA UI
    # ======================================

    def _construir_cabecalho(self):

        cabecalho = QFrame()
        cabecalho.setStyleSheet(f"background:{tokens.SIDEBAR};")
        cabecalho.setFixedHeight(64)

        cab_layout = QHBoxLayout(cabecalho)
        cab_layout.setContentsMargins(24, 0, 24, 0)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("PAGAMENTO")
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

        cab_layout.addLayout(col_titulo)
        cab_layout.addStretch()
        cab_layout.addWidget(self.bt_cancelar)

        return cabecalho

    def _construir_coluna_resumo(self):

        esquerda = QFrame()
        esquerda.setFixedWidth(320)
        esquerda.setStyleSheet(
            f"background:{tokens.FUNDO}; "
            f"border-right:1px solid {tokens.BORDA};"
        )

        esq_layout = QVBoxLayout(esquerda)
        esq_layout.setContentsMargins(24, 24, 24, 24)
        esq_layout.setSpacing(4)

        lbl_total_titulo = QLabel("TOTAL DA VENDA")
        lbl_total_titulo.setStyleSheet(
            f"background:transparent; font-size:11px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO};"
        )

        self.lbl_total = QLabel(f"R$ {_fmt(self.total)}")
        self.lbl_total.setStyleSheet(
            f"background:transparent; font-size:34px; "
            f"font-weight:800; color:{tokens.TEXTO};"
        )

        esq_layout.addWidget(lbl_total_titulo)
        esq_layout.addWidget(self.lbl_total)
        esq_layout.addSpacing(16)

        lbl_resumo_titulo = QLabel(f"RESUMO · {len(self.itens)} ITENS")
        lbl_resumo_titulo.setStyleSheet(
            f"background:transparent; font-size:11px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO};"
        )

        esq_layout.addWidget(lbl_resumo_titulo)

        for item in self.itens:

            linha_item = QHBoxLayout()

            nome = QLabel(item["nome"])
            nome.setStyleSheet(
                f"background:transparent; font-size:12px; color:{tokens.TEXTO};"
            )

            subtotal = item["preco"] * item["quantidade"]

            valor = QLabel(f"R$ {_fmt(subtotal)}")
            valor.setAlignment(Qt.AlignRight)
            valor.setStyleSheet(
                f"background:transparent; font-size:12px; color:{tokens.TEXTO};"
            )

            linha_item.addWidget(nome)
            linha_item.addWidget(valor)

            esq_layout.addLayout(linha_item)

        esq_layout.addStretch()

        # ---- resumo do pagamento (pago / restante), sempre visivel ----

        linha_divisoria = QFrame()
        linha_divisoria.setFixedHeight(1)
        linha_divisoria.setStyleSheet(f"background:{tokens.BORDA}; border:none;")
        esq_layout.addWidget(linha_divisoria)
        esq_layout.addSpacing(12)

        linha_pago = QHBoxLayout()
        lbl_pago_titulo = QLabel("PAGO")
        lbl_pago_titulo.setStyleSheet(
            f"background:transparent; font-size:12px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO};"
        )
        self.lbl_pago = QLabel(f"R$ {_fmt(0)}")
        self.lbl_pago.setAlignment(Qt.AlignRight)
        self.lbl_pago.setStyleSheet(
            f"background:transparent; font-size:14px; "
            f"font-weight:bold; color:{tokens.TEXTO};"
        )
        linha_pago.addWidget(lbl_pago_titulo)
        linha_pago.addWidget(self.lbl_pago)
        esq_layout.addLayout(linha_pago)

        linha_restante = QHBoxLayout()
        lbl_restante_titulo = QLabel("RESTANTE")
        lbl_restante_titulo.setStyleSheet(
            f"background:transparent; font-size:12px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO};"
        )
        self.lbl_restante = QLabel(f"R$ {_fmt(self.total)}")
        self.lbl_restante.setAlignment(Qt.AlignRight)
        self.lbl_restante.setStyleSheet(
            f"background:transparent; font-size:18px; "
            f"font-weight:800; color:{tokens.ALERTA};"
        )
        linha_restante.addWidget(lbl_restante_titulo)
        linha_restante.addWidget(self.lbl_restante)
        esq_layout.addLayout(linha_restante)

        return esquerda

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

        self.lbl_forma_titulo = QLabel("FORMA DE PAGAMENTO")
        self.lbl_forma_titulo.setStyleSheet(
            f"background:transparent; font-size:11px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO};"
        )
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
            "+ DIVIDIR PAGAMENTO", icone_nome="plus"
        )
        self.bt_dividir.setAutoDefault(False)
        self.bt_dividir.setMinimumHeight(40)
        self.bt_dividir.clicked.connect(self.ativar_divisao)
        layout.addWidget(self.bt_dividir)

        self.bloco_divisao = self._construir_bloco_divisao()
        self.bloco_divisao.setVisible(False)
        layout.addWidget(self.bloco_divisao)

        # ---- entrada de valor (dinheiro / troco) ----

        self.bloco_dinheiro = self._construir_bloco_dinheiro()
        layout.addWidget(self.bloco_dinheiro)

        # ---- QR Code (pix) ----

        self.bloco_pix = self._construir_bloco_pix()
        layout.addWidget(self.bloco_pix)

        self.gerar_qrcode_pix()

        # ---- fiado (a prazo) ----

        self.bloco_prazo = self._construir_bloco_prazo()
        layout.addWidget(self.bloco_prazo)

        # ---- observação (opcional) ----

        lbl_obs_titulo = QLabel("OBSERVAÇÃO (OPCIONAL)")
        lbl_obs_titulo.setStyleSheet(
            f"background:transparent; font-size:11px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO};"
        )

        self.observacao = CampoTexto(
            "Ex.: cliente pediu embalagem pra presente"
        )

        layout.addWidget(lbl_obs_titulo)
        layout.addWidget(self.observacao)

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

        self.bt_confirmar = BotaoSucesso("CONFIRMAR VENDA", icone_nome="check")
        self.bt_confirmar.setMinimumHeight(52)
        self.bt_confirmar.setAutoDefault(True)
        self.bt_confirmar.setDefault(True)
        self.bt_confirmar.clicked.connect(self.confirmar)

        rodape_layout.addWidget(self.bt_confirmar)

        dir_layout.addWidget(rodape)

        return direita

    def _construir_bloco_divisao(self):

        bloco = QFrame()
        bloco.setObjectName("blocoDivisao")
        bloco.setStyleSheet(f"""
            QFrame#blocoDivisao {{
                background: {tokens.PRIMARIA_CLARA};
                border: 1.5px solid {tokens.PRIMARIA};
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
                background:{tokens.CARD};
                font-size:22px;
                font-weight:800;
                color:{tokens.TEXTO};
                border:1.5px solid {tokens.BORDA_FORTE};
                border-radius:{tokens.RADIUS_SM}px;
                padding:6px 12px;
            }}
            QLineEdit:focus {{
                border:1.5px solid {tokens.PRIMARIA};
            }}
        """)

        return campo

    def _construir_bloco_dinheiro(self):

        bloco = QFrame()

        bloco_layout = QVBoxLayout(bloco)
        bloco_layout.setContentsMargins(0, 0, 0, 0)
        bloco_layout.setSpacing(10)

        lbl_entrada_titulo = QLabel("DINHEIRO RECEBIDO DO CLIENTE")
        lbl_entrada_titulo.setStyleSheet(
            f"background:transparent; font-size:11px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO};"
        )

        self.recebido = QLineEdit()
        self.recebido.setPlaceholderText("R$ 0,00")
        self.recebido.setAlignment(Qt.AlignRight)
        self.recebido.setStyleSheet(f"""
            QLineEdit {{
                background:transparent;
                font-size:32px;
                font-weight:800;
                color:{tokens.TEXTO};
                border:none;
                border-bottom:2px solid {tokens.BORDA};
                padding:6px 0;
            }}
            QLineEdit:focus {{
                border-bottom:2px solid {tokens.PRIMARIA};
            }}
        """)
        self.recebido.textEdited.connect(self._recebido_editado)

        bloco_layout.addWidget(lbl_entrada_titulo)
        bloco_layout.addWidget(self.recebido)

        valores_layout = QGridLayout()
        valores_layout.setSpacing(8)

        for indice, valor in enumerate(VALORES_RAPIDOS):

            bt = QPushButton(f"+R$ {valor}")
            bt.setAutoDefault(False)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setMinimumHeight(36)
            bt.setStyleSheet(f"""
                QPushButton {{
                    background:{tokens.FUNDO};
                    color:{tokens.TEXTO};
                    border-radius:{tokens.RADIUS_SM}px;
                    font-weight:600;
                }}
                QPushButton:hover {{
                    background:{tokens.BORDA};
                }}
            """)
            bt.clicked.connect(
                lambda checked, v=valor: self.adicionar_valor(v)
            )

            valores_layout.addWidget(bt, indice // 4, indice % 4)

        bloco_layout.addLayout(valores_layout)

        self.troco = QLabel("Troco: R$ 0,00")
        self.troco.setStyleSheet(
            f"background:transparent; font-size:15px; "
            f"font-weight:800; color:{tokens.TEXTO};"
        )

        bloco_layout.addWidget(self.troco)

        return bloco

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

    def _construir_bloco_prazo(self):

        bloco = QFrame()

        prazo_layout = QVBoxLayout(bloco)
        prazo_layout.setContentsMargins(0, 0, 0, 0)
        prazo_layout.setSpacing(10)

        lbl_prazo_titulo = QLabel("CLIENTE DO FIADO")
        lbl_prazo_titulo.setStyleSheet(
            f"background:transparent; font-size:11px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO};"
        )

        self.lbl_cliente_selecionado = QLabel(
            self.cliente_nome or "Nenhum cliente selecionado"
        )
        self.lbl_cliente_selecionado.setWordWrap(True)
        self.lbl_cliente_selecionado.setStyleSheet(f"""
            background:transparent; font-size:16px; font-weight:bold;
            color: {tokens.SECUNDARIA if self.cliente_nome else tokens.ERRO};
        """)

        self.bt_selecionar_cliente = BotaoSecundario(
            "Selecionar Cliente", icone_nome="user"
        )
        self.bt_selecionar_cliente.setMinimumHeight(44)
        self.bt_selecionar_cliente.setAutoDefault(False)
        self.bt_selecionar_cliente.clicked.connect(
            self.abrir_selecionar_cliente
        )

        prazo_layout.addWidget(lbl_prazo_titulo)
        prazo_layout.addWidget(self.lbl_cliente_selecionado)
        prazo_layout.addWidget(self.bt_selecionar_cliente)

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

        self.lbl_forma_titulo.setText(
            "1ª FORMA DE PAGAMENTO" if self.dividir_pagamento
            else "FORMA DE PAGAMENTO"
        )

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
        self.bloco_prazo.setVisible(
            self.forma_pagamento == "PRAZO" or forma_2 == "PRAZO"
        )

    # ======================================
    # DIVIDIR PAGAMENTO
    # ======================================

    def ativar_divisao(self):

        self.dividir_pagamento = True

        self.bt_dividir.setVisible(False)
        self.bloco_divisao.setVisible(True)
        fade_in(self.bloco_divisao)

        self.lbl_forma_titulo.setText("1ª FORMA DE PAGAMENTO")
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

        self.lbl_forma_titulo.setText("FORMA DE PAGAMENTO")
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
                f"background:transparent; font-size:18px; "
                f"font-weight:800; color:{tokens.ALERTA};"
            )
        else:
            self.lbl_restante.setStyleSheet(
                f"background:transparent; font-size:18px; "
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
                    border:1.5px solid {tokens.ERRO};
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
                    border:1.5px solid {tokens.ALERTA};
                    border-radius:{tokens.RADIUS_MD}px;
                }}
            """)
            self.lbl_status_rotulo.setStyleSheet(
                "background:transparent; font-size:11px; "
                "font-weight:800; color:#B45309;"
            )
            self.lbl_status_rotulo.setText("FALTA RECEBER")
            self.lbl_status_valor.setStyleSheet(
                "background:transparent; font-size:22px; "
                "font-weight:800; color:#B45309;"
            )
            self.lbl_status_valor.setText(f"R$ {_fmt(restante)}")

        else:

            self.banner_status.setStyleSheet(f"""
                QFrame#bannerStatus {{
                    background:{tokens.SUCESSO_CLARO};
                    border:1.5px solid {tokens.SECUNDARIA};
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
            return False, "Selecione o cliente do fiado."

        return True, None

    def calcular_troco(self):

        necessario = self._valor_dinheiro_necessario()

        if necessario is None:
            self.troco.setText("Troco: R$ 0,00")
            return

        recebido = _texto_para_valor(self.recebido.text())

        troco = max(0.0, recebido - necessario)

        cor = tokens.SECUNDARIA if troco > EPSILON else tokens.TEXTO
        self.troco.setStyleSheet(
            f"background:transparent; font-size:15px; "
            f"font-weight:800; color:{cor};"
        )
        self.troco.setText(f"Troco: R$ {_fmt(troco)}")

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
            f"background:transparent; font-size:16px; "
            f"font-weight:bold; color:{tokens.SECUNDARIA};"
        )

        self._atualizar_estado_confirmar()

    def gerar_qrcode_pix(self):

        config = configuracoes()

        chave = (config.get("pix_chave") or "").strip()

        if not chave:

            self.lbl_qrcode.setText("QR Code indisponível")
            self.lbl_pix_info.setText(
                "Cadastre uma chave PIX em Configurações "
                "para gerar o QR Code de cobrança."
            )

            return

        nome = config.get("pix_nome") or config.get("nome_loja") or "LOJA"
        cidade = config.get("pix_cidade") or ""

        payload = montar_payload_pix(
            chave=chave,
            nome=nome,
            cidade=cidade,
            valor=self.valor_principal(),
        )

        imagem = qrcode.make(payload)

        buffer = BytesIO()
        imagem.save(buffer, format="PNG")

        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue())

        self.lbl_qrcode.setPixmap(
            pixmap.scaled(
                200,
                200,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

        self.lbl_pix_info.setText(
            f"Aponte a câmera do banco para pagar "
            f"R$ {_fmt(self.valor_principal())} via PIX para {chave}"
        )

    def adicionar_valor(self, valor):

        self.recebido_acumulado += valor

        self.recebido.setText(_fmt(self.recebido_acumulado))
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
