from io import BytesIO

import qrcode
from PySide6.QtCore import Qt, QSize, QTimer, QRegularExpression
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut, QRegularExpressionValidator
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
)

from design import tokens
from design.icons import icone, icone_pixmap
from design.responsive import tamanho_fixo_seguro
from design.widgets import (
    BotaoSecundario, BotaoSucesso, CabecalhoDialogo, CampoTexto, cor_forma_pagamento,
    estilo_botao_forma,
)
from services.api import configuracoes
from services.pix_utils import montar_payload_pix
from services.worker import rodar_em_thread
from telas.selecionar_cliente import SelecionarClienteDialog
from utils.formatacao import formatar_moeda

# rotulo exibido, valor enviado pra API, icone (lucide) do botao -- a
# ordem aqui e' a tecla de atalho (1 = Dinheiro, 2 = Debito...)
FORMAS = [
    ("Dinheiro", "DINHEIRO", "dollar-sign"),
    ("Débito", "DEBITO", "credit-card"),
    ("Crédito", "CREDITO", "credit-card"),
    ("PIX", "PIX", "refresh-cw"),
    ("Crediário", "PRAZO", "calendar"),
]

NOMES_FORMA = {valor: rotulo for rotulo, valor, _icone in FORMAS}
ICONES_FORMA = {valor: icone_nome for _rotulo, valor, icone_nome in FORMAS}

# notas mais comuns -- o botao poe o valor da nota no campo (o cliente
# entregou uma nota de 50), nao soma
NOTAS = [2, 5, 10, 20, 50, 100, 200]

# a venda guarda no maximo 2 formas (forma_pagamento + forma_pagamento_2
# no backend), e as duas precisam ser diferentes
MAX_FORMAS = 2

# tolerancia de meio-centavo pra comparacao de valores em ponto flutuante
EPSILON = 0.005


def _texto_para_valor(texto):
    """Aceita '50', '50,5', '1.234,56' e '1234.56'."""
    texto = (texto or "").strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return round(float(texto or 0), 2)
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
    """Tela de pagamento no formato de PDV: escolhe a forma (tecla 1-5),
    o valor ja vem com o que falta, Enter lanca. Da' pra lancar ate' 2
    formas; so' dinheiro pode passar do que falta (vira troco). Com a
    venda quitada, Enter/F3 finaliza.

    O PDV le daqui: forma_pagamento, forma_pagamento_2, valor_forma_2,
    cliente_id, cliente_nome e observacao.text()."""

    def __init__(
        self, total, itens=None, cliente_id=None, cliente_nome=None,
        desconto=0.0, acrescimo=0.0,
    ):

        super().__init__()

        self.total = round(total, 2)
        self.itens = itens or []
        self.subtotal = sum(item["preco"] * item["quantidade"] for item in self.itens)
        self.desconto = desconto or 0.0
        self.acrescimo = acrescimo or 0.0
        self.cliente_id = cliente_id
        self.cliente_nome = cliente_nome

        # pagamentos lancados: [{"forma", "valor" (o que abate da
        # venda), "entregue" (o que o cliente deu -- > valor so' em
        # dinheiro, a diferenca e' o troco)}]
        self.pagamentos = []
        self.forma_atual = None
        self._enter_do_lancamento = False

        # resultado lido pelo PDV depois do accept()
        self.forma_pagamento = None
        self.forma_pagamento_2 = None
        self.valor_forma_2 = 0.0

        self._timer_pix = QTimer(self)
        self._timer_pix.setSingleShot(True)
        self._timer_pix.setInterval(400)
        self._timer_pix.timeout.connect(self.gerar_qrcode_pix)

        self.setWindowTitle("Pagamento")
        tamanho_fixo_seguro(self, 1140, 800)
        self.setStyleSheet(f"background:{tokens.CARD};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        raiz.addWidget(self._construir_cabecalho())
        raiz.addWidget(self._construir_faixa_totais())

        corpo = QHBoxLayout()
        corpo.setContentsMargins(0, 0, 0, 0)
        corpo.setSpacing(0)

        corpo.addWidget(self._construir_coluna_formas())
        corpo.addWidget(self._construir_coluna_valor(), stretch=1)

        raiz.addLayout(corpo, stretch=1)

        raiz.addWidget(self._construir_barra_atalhos())

        self._atalho_cliente = QShortcut(QKeySequence("F2"), self)
        self._atalho_cliente.activated.connect(self.abrir_selecionar_cliente)

        self._atalho_finalizar = QShortcut(QKeySequence("F3"), self)
        self._atalho_finalizar.activated.connect(self.confirmar)

        self._atualizar_tela()

    def showEvent(self, event):
        super().showEvent(event)
        # entra com o foco na lista de formas, Dinheiro marcado -- Enter
        # ja' escolhe dinheiro, ou 1-5 escolhe outra
        self.botoes_forma["DINHEIRO"].setFocus()

    # ======================================
    # CONSTRUCAO DA UI
    # ======================================

    def _construir_cabecalho(self):
        """Topo claro no padrão das outras subtelas (CabecalhoDialogo):
        ícone, "Pagamento" e o resumo da venda embaixo; o Cancelar (Esc)
        fica na ponta direita, no lugar do X."""

        qtd = len(self.itens)
        detalhe = f"{qtd} {'item' if qtd == 1 else 'itens'}  ·  Subtotal R$ {_fmt(self.subtotal)}"
        if self.desconto > EPSILON:
            detalhe += f"  ·  Desconto R$ {_fmt(self.desconto)}"
        if self.acrescimo > EPSILON:
            detalhe += f"  ·  Acréscimo R$ {_fmt(self.acrescimo)}"

        cabecalho = CabecalhoDialogo(
            "credit-card", tokens.PRIMARIA, tokens.PRIMARIA_CLARA,
            "Pagamento", detalhe,
        )

        self.bt_cancelar = BotaoSecundario("Cancelar (Esc)", icone_nome="x")
        self.bt_cancelar.setAutoDefault(False)
        self.bt_cancelar.setFocusPolicy(Qt.NoFocus)
        self.bt_cancelar.clicked.connect(self.reject)
        # a primeira linha do CabecalhoDialogo termina num stretch --
        # o botão entra depois dele, na ponta direita
        cabecalho.layout().itemAt(0).layout().addWidget(self.bt_cancelar)

        return cabecalho

    def _construir_faixa_totais(self):
        """TOTAL / PAGO / FALTA (vira TROCO) -- os 3 numeros que o
        operador olha, grandes e sempre no mesmo lugar."""

        faixa = QFrame()
        faixa.setStyleSheet(
            f"background:{tokens.FUNDO}; border-bottom:1px solid {tokens.BORDA};"
        )

        layout = QHBoxLayout(faixa)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(14)

        caixa_total, _rot, self.lbl_total = self._caixa_numero("TOTAL")
        caixa_pago, _rot, self.lbl_pago = self._caixa_numero("PAGO")
        self.caixa_falta, self.lbl_falta_rotulo, self.lbl_falta = self._caixa_numero("FALTA")

        self.lbl_total.setText(f"R$ {_fmt(self.total)}")

        layout.addWidget(caixa_total, 1)
        layout.addWidget(caixa_pago, 1)
        layout.addWidget(self.caixa_falta, 1)

        return faixa

    def _caixa_numero(self, rotulo):

        caixa = QFrame()
        caixa.setObjectName("caixaNumero")

        layout = QVBoxLayout(caixa)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(0)

        lbl_rotulo = QLabel(rotulo)
        lbl_valor = QLabel("R$ 0,00")
        lbl_valor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(lbl_rotulo)
        layout.addWidget(lbl_valor)

        self._pintar_caixa_numero(caixa, lbl_rotulo, lbl_valor, tokens.CARD, tokens.TEXTO)

        return caixa, lbl_rotulo, lbl_valor

    @staticmethod
    def _pintar_caixa_numero(caixa, lbl_rotulo, lbl_valor, fundo, cor):

        caixa.setStyleSheet(f"""
            QFrame#caixaNumero {{
                background:{fundo};
                border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_MD}px;
            }}
        """)
        lbl_rotulo.setStyleSheet(
            f"background:transparent; border:none; font-size:11px; "
            f"font-weight:800; color:{cor};"
        )
        lbl_valor.setStyleSheet(
            f"background:transparent; border:none; font-size:28px; "
            f"font-weight:800; color:{cor};"
        )

    def _construir_coluna_formas(self):

        coluna = QFrame()
        coluna.setFixedWidth(330)
        coluna.setStyleSheet(
            f"background:{tokens.FUNDO}; border-right:1px solid {tokens.BORDA};"
        )

        layout = QVBoxLayout(coluna)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)

        layout.addWidget(self._rotulo_secao("FORMA DE PAGAMENTO"))

        self.botoes_forma = {}

        for numero, (rotulo, valor, icone_nome) in enumerate(FORMAS, start=1):

            bt = QPushButton(f"  {numero}   {rotulo}")
            bt.setAutoDefault(False)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setMinimumHeight(58)
            bt.setIconSize(QSize(18, 18))
            bt.clicked.connect(lambda checked=False, v=valor: self.selecionar_forma(v))

            self.botoes_forma[valor] = bt
            layout.addWidget(bt)

        layout.addSpacing(10)
        layout.addWidget(self._construir_linha_cliente())

        layout.addSpacing(6)
        layout.addWidget(self._rotulo_secao("OBSERVAÇÃO (OPCIONAL)"))

        self.observacao = CampoTexto("Ex.: embalar pra presente")
        layout.addWidget(self.observacao)

        layout.addStretch()

        return coluna

    def _rotulo_secao(self, texto):

        lbl = QLabel(texto)
        lbl.setStyleSheet(
            f"background:transparent; border:none; font-size:11px; "
            f"font-weight:bold; color:{tokens.TEXTO_SECUNDARIO};"
        )
        return lbl

    def _construir_linha_cliente(self):

        linha = QFrame()
        linha.setObjectName("linhaCliente")
        linha.setStyleSheet(f"""
            QFrame#linhaCliente {{
                background: {tokens.CARD};
                border:1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        icone_cliente = QLabel()
        icone_cliente.setPixmap(icone_pixmap("user", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        icone_cliente.setStyleSheet("background:transparent; border:none;")
        layout.addWidget(icone_cliente)

        col_cliente = QVBoxLayout()
        col_cliente.setSpacing(0)

        lbl_rotulo = QLabel("CLIENTE")
        lbl_rotulo.setStyleSheet(
            f"background:transparent; border:none; font-size:10px; "
            f"font-weight:bold; color:{tokens.TEXTO_TERCIARIO};"
        )
        col_cliente.addWidget(lbl_rotulo)

        self.lbl_cliente_selecionado = QLabel()
        self.lbl_cliente_selecionado.setWordWrap(True)
        col_cliente.addWidget(self.lbl_cliente_selecionado)
        self._pintar_cliente()

        layout.addLayout(col_cliente, 1)

        self.bt_selecionar_cliente = QPushButton("F2")
        self.bt_selecionar_cliente.setCursor(Qt.PointingHandCursor)
        self.bt_selecionar_cliente.setAutoDefault(False)
        self.bt_selecionar_cliente.setFocusPolicy(Qt.NoFocus)
        self.bt_selecionar_cliente.setToolTip("Selecionar cliente (F2)")
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

    def _pintar_cliente(self):

        self.lbl_cliente_selecionado.setText(self.cliente_nome or "Não informado")
        cor = tokens.SECUNDARIA if self.cliente_nome else tokens.TEXTO_SECUNDARIO
        self.lbl_cliente_selecionado.setStyleSheet(
            f"background:transparent; border:none; font-size:13px; "
            f"font-weight:700; color:{cor};"
        )

    def _construir_coluna_valor(self):

        coluna = QFrame()
        coluna.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(coluna)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(10)

        # ---- valor da forma escolhida ----

        self.bloco_valor = QFrame()
        bloco_layout = QVBoxLayout(self.bloco_valor)
        bloco_layout.setContentsMargins(0, 0, 0, 0)
        bloco_layout.setSpacing(8)

        self.lbl_valor_titulo = self._rotulo_secao("VALOR")
        bloco_layout.addWidget(self.lbl_valor_titulo)

        self.caixa_valor = QFrame()
        self.caixa_valor.setObjectName("caixaValor")
        self.caixa_valor.setStyleSheet(f"""
            QFrame#caixaValor {{
                background: {tokens.PRIMARIA_CLARA};
                border:2px solid {tokens.PRIMARIA};
                border-radius: {tokens.RADIUS_SM}px;
            }}
        """)
        caixa_layout = QHBoxLayout(self.caixa_valor)
        caixa_layout.setContentsMargins(16, 2, 16, 2)

        lbl_prefixo = QLabel("R$")
        lbl_prefixo.setStyleSheet(
            f"background:transparent; border:none; font-size:22px; "
            f"font-weight:700; color:{tokens.TEXTO_TERCIARIO};"
        )
        caixa_layout.addWidget(lbl_prefixo)

        self.campo_valor = QLineEdit()
        self.campo_valor.setAlignment(Qt.AlignRight)
        self.campo_valor.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"[0-9.,]{0,12}"), self)
        )
        self.campo_valor.setStyleSheet(f"""
            QLineEdit {{
                background:transparent; border:none;
                font-size:32px; font-weight:800;
                color:{tokens.TEXTO}; padding:6px 0;
            }}
        """)
        self.campo_valor.returnPressed.connect(self.lancar_pagamento)
        self.campo_valor.textEdited.connect(self._valor_editado)
        caixa_layout.addWidget(self.campo_valor)

        bloco_layout.addWidget(self.caixa_valor)

        self.lbl_dica_valor = QLabel("Enter lança o pagamento  ·  Esc volta pras formas")
        self.lbl_dica_valor.setStyleSheet(
            f"background:transparent; font-size:11px; color:{tokens.TEXTO_TERCIARIO};"
        )
        bloco_layout.addWidget(self.lbl_dica_valor)

        # notas -- so' em dinheiro
        self.bloco_notas = QFrame()
        grade = QGridLayout(self.bloco_notas)
        grade.setContentsMargins(0, 4, 0, 0)
        grade.setSpacing(6)

        botoes_notas = [(f"R$ {n}", n) for n in NOTAS] + [("Exato", None)]
        for indice, (rotulo, nota) in enumerate(botoes_notas):
            bt = QPushButton(rotulo)
            bt.setAutoDefault(False)
            bt.setFocusPolicy(Qt.NoFocus)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setMinimumHeight(34)
            destaque = nota is None
            bt.setStyleSheet(f"""
                QPushButton {{
                    background:{tokens.PRIMARIA_CLARA if destaque else tokens.FUNDO};
                    color:{tokens.PRIMARIA_HOVER if destaque else tokens.TEXTO};
                    border:1px solid {tokens.BORDA};
                    border-radius:{tokens.RADIUS_SM}px;
                    font-weight:700; font-size:12px;
                }}
                QPushButton:hover {{ border-color:{tokens.PRIMARIA}; }}
            """)
            bt.clicked.connect(lambda checked=False, n=nota: self._usar_nota(n))
            grade.addWidget(bt, indice // 4, indice % 4)

        bloco_layout.addWidget(self.bloco_notas)

        # QR Code -- so' em PIX
        self.bloco_pix = QFrame()
        pix_layout = QHBoxLayout(self.bloco_pix)
        pix_layout.setContentsMargins(0, 4, 0, 0)
        pix_layout.setSpacing(14)

        self.lbl_qrcode = QLabel()
        self.lbl_qrcode.setAlignment(Qt.AlignCenter)
        self.lbl_qrcode.setFixedSize(170, 170)
        self.lbl_qrcode.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO}; font-size:12px;"
        )

        self.lbl_pix_info = QLabel()
        self.lbl_pix_info.setWordWrap(True)
        self.lbl_pix_info.setStyleSheet(
            f"background:transparent; font-size:12px; color:{tokens.TEXTO_SECUNDARIO};"
        )

        pix_layout.addWidget(self.lbl_qrcode)
        pix_layout.addWidget(self.lbl_pix_info, 1)

        bloco_layout.addWidget(self.bloco_pix)

        layout.addWidget(self.bloco_valor)

        # aviso quando nenhuma forma foi escolhida ainda
        self.lbl_escolha_forma = QLabel(
            "Escolha a forma de pagamento (teclas 1 a 5)"
        )
        self.lbl_escolha_forma.setAlignment(Qt.AlignCenter)
        self.lbl_escolha_forma.setMinimumHeight(90)
        self.lbl_escolha_forma.setStyleSheet(f"""
            background:{tokens.FUNDO}; color:{tokens.TEXTO_SECUNDARIO};
            border:1px dashed {tokens.BORDA}; border-radius:{tokens.RADIUS_SM}px;
            font-size:14px; font-weight:600;
        """)
        layout.addWidget(self.lbl_escolha_forma)

        # ---- pagamentos lancados ----

        layout.addSpacing(6)
        layout.addWidget(self._rotulo_secao("PAGAMENTOS LANÇADOS"))

        self.lista_pagamentos = QVBoxLayout()
        self.lista_pagamentos.setSpacing(6)
        layout.addLayout(self.lista_pagamentos)

        self.lbl_sem_pagamentos = QLabel("Nenhum pagamento lançado.")
        self.lbl_sem_pagamentos.setStyleSheet(
            f"background:transparent; font-size:12px; color:{tokens.TEXTO_TERCIARIO};"
        )
        layout.addWidget(self.lbl_sem_pagamentos)

        layout.addStretch()

        # ---- rodape: aviso + finalizar ----

        self.lbl_aviso = QLabel("")
        self.lbl_aviso.setAlignment(Qt.AlignCenter)
        self.lbl_aviso.setWordWrap(True)
        self.lbl_aviso.setVisible(False)
        self.lbl_aviso.setStyleSheet(
            f"background:transparent; font-size:12px; "
            f"font-weight:600; color:{tokens.ERRO};"
        )
        layout.addWidget(self.lbl_aviso)

        self.bt_confirmar = BotaoSucesso("FINALIZAR VENDA (F3)", icone_nome="check")
        self.bt_confirmar.setMinimumHeight(52)
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.clicked.connect(self.confirmar)
        layout.addWidget(self.bt_confirmar)

        return coluna

    def _construir_barra_atalhos(self):

        barra = QFrame()
        barra.setFixedHeight(36)
        barra.setStyleSheet(f"""
            QFrame {{
                background: {tokens.FUNDO};
                border-top: 1px solid {tokens.BORDA};
            }}
        """)

        layout = QHBoxLayout(barra)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(18)

        for tecla, rotulo in (
            ("1-5", "Forma"),
            ("Enter", "Lançar / Finalizar"),
            ("Del", "Remover pagamento"),
            ("F2", "Cliente"),
            ("F3", "Finalizar"),
            ("Esc", "Voltar / Cancelar"),
        ):
            layout.addLayout(self._item_atalho(tecla, rotulo))

        layout.addStretch()

        return barra

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
            f"background:transparent; border:none; color:{tokens.TEXTO_TERCIARIO}; font-size:11px;"
        )

        item.addWidget(badge_tecla)
        item.addWidget(lbl_rotulo)

        return item

    # ======================================
    # CONTAS
    # ======================================

    def pago(self):
        return round(sum(p["valor"] for p in self.pagamentos), 2)

    def falta(self):
        return round(max(0.0, self.total - self.pago()), 2)

    def troco(self):
        return round(sum(p["entregue"] - p["valor"] for p in self.pagamentos), 2)

    def quitado(self):
        return self.total - self.pago() <= EPSILON

    # ======================================
    # TECLADO
    # ======================================

    def keyPressEvent(self, event):

        tecla = event.key()
        no_valor = self.campo_valor.hasFocus()
        enter = tecla in (Qt.Key_Return, Qt.Key_Enter)

        # o Enter que lancou o pagamento no campo de valor sobe pra ca'
        # depois, com o foco ja' no Finalizar -- nao pode fechar a venda
        # antes do operador ver o troco
        if enter and self._enter_do_lancamento:
            self._enter_do_lancamento = False
            return

        if tecla == Qt.Key_Escape:
            # Esc no campo de valor volta pras formas; fora dele cancela
            if no_valor:
                self._voltar_para_formas()
            else:
                self.reject()
            return

        if no_valor:
            super().keyPressEvent(event)
            return

        if Qt.Key_1 <= tecla <= Qt.Key_1 + len(FORMAS) - 1:
            self.selecionar_forma(FORMAS[tecla - Qt.Key_1][1])
            return

        if tecla in (Qt.Key_Delete, Qt.Key_Backspace):
            if self.pagamentos:
                self.remover_pagamento(len(self.pagamentos) - 1)
            return

        if enter:
            if self.quitado():
                self.confirmar()
                return
            focado = self.focusWidget()
            for valor, bt in self.botoes_forma.items():
                if bt is focado:
                    self.selecionar_forma(valor)
                    return
            return

        if tecla in (Qt.Key_Up, Qt.Key_Down):
            self._mover_foco_formas(-1 if tecla == Qt.Key_Up else 1)
            return

        super().keyPressEvent(event)

    def _mover_foco_formas(self, passo):

        chaves = [valor for _r, valor, _i in FORMAS]
        focado = self.focusWidget()
        atual = next(
            (i for i, c in enumerate(chaves) if self.botoes_forma[c] is focado), -1
        )
        novo = (atual + passo) % len(chaves)
        self.botoes_forma[chaves[novo]].setFocus()

    # ======================================
    # FORMA / VALOR / LANCAMENTO
    # ======================================

    def selecionar_forma(self, valor):

        if self.quitado():
            self._avisar("A venda já está paga. Enter ou F3 finaliza.")
            self.bt_confirmar.setFocus()
            return

        ja_lancada = any(p["forma"] == valor for p in self.pagamentos)

        if len(self.pagamentos) >= MAX_FORMAS and not ja_lancada:
            self._avisar(
                "No máximo 2 formas por venda. Remova um pagamento (Del) "
                "pra trocar."
            )
            return

        if valor == "PRAZO" and self.cliente_id is None:
            self.abrir_selecionar_cliente()
            if self.cliente_id is None:
                self._avisar("Crediário precisa de um cliente (F2).")
                return

        self.forma_atual = valor
        self._avisar(None)

        self.campo_valor.setText(_fmt(self.falta()))
        self._atualizar_tela()

        self.campo_valor.setFocus()
        self.campo_valor.selectAll()

        if valor == "PIX":
            self.gerar_qrcode_pix()

    def _voltar_para_formas(self):

        forma = self.forma_atual or "DINHEIRO"
        self.forma_atual = None
        self._avisar(None)
        self._atualizar_tela()
        self.botoes_forma[forma].setFocus()

    def _valor_editado(self, _texto):

        self._avisar(None)
        if self.forma_atual == "PIX":
            self._timer_pix.start()

    def _usar_nota(self, nota):

        valor = self.falta() if nota is None else nota
        self.campo_valor.setText(_fmt(valor))
        self.campo_valor.setFocus()

    def lancar_pagamento(self):

        forma = self.forma_atual
        if forma is None:
            return

        valor = _texto_para_valor(self.campo_valor.text())
        falta = self.falta()

        if valor <= EPSILON:
            self._avisar("Informe um valor maior que zero.")
            self.campo_valor.selectAll()
            return

        troco = 0.0
        if valor - falta > EPSILON:
            if forma != "DINHEIRO":
                self._avisar(
                    f"{NOMES_FORMA[forma]} não pode passar do que falta "
                    f"(R$ {_fmt(falta)}). Só dinheiro gera troco."
                )
                self.campo_valor.setText(_fmt(falta))
                self.campo_valor.selectAll()
                return
            troco = round(valor - falta, 2)

        existente = next((p for p in self.pagamentos if p["forma"] == forma), None)
        if existente:
            existente["valor"] = round(existente["valor"] + valor - troco, 2)
            existente["entregue"] = round(existente["entregue"] + valor, 2)
        else:
            self.pagamentos.append(
                {"forma": forma, "valor": round(valor - troco, 2), "entregue": valor}
            )

        self.forma_atual = None
        self._atualizar_tela()

        self._enter_do_lancamento = True
        QTimer.singleShot(0, self._limpar_enter_do_lancamento)

        if self.quitado():
            self.bt_confirmar.setFocus()
        else:
            # repetir a forma so' soma nela; o comum e' a proxima ser
            # outra, entao o foco vai pra 1a ainda nao lancada
            livre = next(
                (v for _r, v, _i in FORMAS
                 if all(p["forma"] != v for p in self.pagamentos)),
                "DINHEIRO",
            )
            self.botoes_forma[livre].setFocus()

    def _limpar_enter_do_lancamento(self):
        self._enter_do_lancamento = False

    def remover_pagamento(self, indice):

        if 0 <= indice < len(self.pagamentos):
            del self.pagamentos[indice]

        self.forma_atual = None
        self._avisar(None)
        self._atualizar_tela()
        self.botoes_forma["DINHEIRO"].setFocus()

    # ======================================
    # ATUALIZACAO DA TELA
    # ======================================

    def _avisar(self, texto):

        self.lbl_aviso.setVisible(bool(texto))
        self.lbl_aviso.setText(texto or "")

    def _atualizar_tela(self):

        # ---- botoes de forma ----
        for rotulo, valor, icone_nome in FORMAS:
            self._pintar_forma(self.botoes_forma[valor], valor, icone_nome)

        # ---- bloco de valor ----
        forma = self.forma_atual
        self.bloco_valor.setVisible(forma is not None)
        self.lbl_escolha_forma.setVisible(forma is None and not self.quitado())

        if forma:
            self.lbl_valor_titulo.setText(f"VALOR EM {NOMES_FORMA[forma].upper()}")
            self.bloco_notas.setVisible(forma == "DINHEIRO")
            self.bloco_pix.setVisible(forma == "PIX")

        # ---- totais ----
        self.lbl_pago.setText(f"R$ {_fmt(self.pago())}")

        troco = self.troco()
        if troco > EPSILON:
            self.lbl_falta_rotulo.setText("TROCO")
            self.lbl_falta.setText(f"R$ {_fmt(troco)}")
            self._pintar_caixa_numero(
                self.caixa_falta, self.lbl_falta_rotulo, self.lbl_falta,
                tokens.SUCESSO_CLARO, tokens.SECUNDARIA_HOVER,
            )
        elif self.quitado():
            self.lbl_falta_rotulo.setText("FALTA")
            self.lbl_falta.setText(f"R$ {_fmt(0)}")
            self._pintar_caixa_numero(
                self.caixa_falta, self.lbl_falta_rotulo, self.lbl_falta,
                tokens.SUCESSO_CLARO, tokens.SECUNDARIA_HOVER,
            )
        else:
            self.lbl_falta_rotulo.setText("FALTA")
            self.lbl_falta.setText(f"R$ {_fmt(self.falta())}")
            self._pintar_caixa_numero(
                self.caixa_falta, self.lbl_falta_rotulo, self.lbl_falta,
                tokens.ALERTA_CLARO, tokens.ALERTA_TEXTO,
            )

        # ---- aviso do meio: o que fazer agora ----
        if self.pagamentos and not self.quitado():
            self.lbl_escolha_forma.setText(
                f"Falta R$ {_fmt(self.falta())}  ·  escolha a 2ª forma (teclas 1 a 5)"
                if len(self.pagamentos) < MAX_FORMAS else
                f"Falta R$ {_fmt(self.falta())}  ·  já são {MAX_FORMAS} formas: "
                "remova uma (Del) pra trocar"
            )
        else:
            self.lbl_escolha_forma.setText("Escolha a forma de pagamento (teclas 1 a 5)")

        # dividir: só na 1ª forma (depois o valor já vem com o que falta)
        self.lbl_dica_valor.setText(
            "Enter lança  ·  pra dividir em 2 formas, digite só a parte desta  ·  Esc volta"
            if not self.pagamentos else
            "Enter lança o restante  ·  Esc volta pras formas"
        )

        # ---- lista de pagamentos ----
        while self.lista_pagamentos.count():
            widget = self.lista_pagamentos.takeAt(0).widget()
            if widget:
                # tira da tela já -- só o deleteLater deixava a linha
                # antiga desenhada até o próximo ciclo (linha "fantasma")
                widget.setParent(None)
                widget.deleteLater()

        for indice, pagamento in enumerate(self.pagamentos):
            self.lista_pagamentos.addWidget(self._linha_pagamento(indice, pagamento))

        self.lbl_sem_pagamentos.setVisible(not self.pagamentos)

        # ---- finalizar ----
        self.bt_confirmar.setEnabled(self.quitado())

    def _pintar_forma(self, botao, valor, icone_nome):

        lancada = any(p["forma"] == valor for p in self.pagamentos)
        atual = valor == self.forma_atual

        # forma que não dá mais pra usar (venda paga, ou já são 2 formas
        # e esta não é uma delas) fica apagada em vez de parecer
        # clicável e só responder com aviso
        bloqueada = not lancada and (
            self.quitado() or len(self.pagamentos) >= MAX_FORMAS
        )

        # cada forma com a sua cor (a mesma do fiado e da despesa);
        # forma que já tem pagamento lançado troca o ícone por um check
        estilo, texto = estilo_botao_forma(
            valor, atual, extra="text-align:left; padding:4px 14px; font-size:15px;",
        )
        if bloqueada:
            texto = tokens.TEXTO_TERCIARIO
            estilo += f"""
                QPushButton {{
                    background:{tokens.FUNDO}; color:{texto}; border:1.5px solid {tokens.BORDA};
                }}
            """
        botao.setStyleSheet(estilo)
        botao.setIcon(icone("check" if lancada and not atual else icone_nome, cor=texto, tamanho=18))

    def _linha_pagamento(self, indice, pagamento):

        forma = pagamento["forma"]
        cor = cor_forma_pagamento(forma)

        # faixa na cor da forma, como os botões à esquerda
        linha = QFrame()
        linha.setObjectName("linhaPagamento")
        linha.setStyleSheet(f"""
            QFrame#linhaPagamento {{
                background:{tokens.FUNDO};
                border:1px solid {tokens.BORDA};
                border-left:4px solid {cor};
                border-radius:{tokens.RADIUS_SM}px;
            }}
        """)

        layout = QHBoxLayout(linha)
        layout.setContentsMargins(12, 10, 8, 10)
        layout.setSpacing(10)

        # venda dividida: deixa claro qual é a 1ª e a 2ª forma
        if len(self.pagamentos) > 1:
            lbl_ordem = QLabel(f"{indice + 1}ª")
            lbl_ordem.setStyleSheet(
                f"background:transparent; border:none; font-size:12px; "
                f"font-weight:800; color:{tokens.TEXTO_TERCIARIO};"
            )
            layout.addWidget(lbl_ordem)

        lbl_icone = QLabel()
        lbl_icone.setPixmap(icone_pixmap(ICONES_FORMA[forma], cor=cor_forma_pagamento(forma), tamanho=16))
        lbl_icone.setStyleSheet("background:transparent; border:none;")
        layout.addWidget(lbl_icone)

        lbl_nome = QLabel(NOMES_FORMA[forma])
        lbl_nome.setStyleSheet(
            f"background:transparent; border:none; font-size:14px; "
            f"font-weight:700; color:{tokens.TEXTO};"
        )
        layout.addWidget(lbl_nome)

        troco = pagamento["entregue"] - pagamento["valor"]
        if troco > EPSILON:
            lbl_entregue = QLabel(
                f"recebido R$ {_fmt(pagamento['entregue'])}  ·  troco R$ {_fmt(troco)}"
            )
            lbl_entregue.setStyleSheet(
                f"background:transparent; border:none; font-size:12px; "
                f"color:{tokens.TEXTO_SECUNDARIO};"
            )
            layout.addWidget(lbl_entregue)

        layout.addStretch()

        lbl_valor = QLabel(f"R$ {_fmt(pagamento['valor'])}")
        lbl_valor.setStyleSheet(
            f"background:transparent; border:none; font-size:16px; "
            f"font-weight:800; color:{tokens.TEXTO};"
        )
        layout.addWidget(lbl_valor)

        bt_remover = QPushButton()
        bt_remover.setIcon(icone("trash-2", cor=tokens.ERRO, tamanho=16))
        bt_remover.setFixedSize(32, 32)
        bt_remover.setAutoDefault(False)
        bt_remover.setFocusPolicy(Qt.NoFocus)
        bt_remover.setCursor(Qt.PointingHandCursor)
        bt_remover.setToolTip("Remover este pagamento")
        bt_remover.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:6px; }}
            QPushButton:hover {{ background:{tokens.ERRO_CLARO}; }}
        """)
        bt_remover.clicked.connect(lambda checked=False, i=indice: self.remover_pagamento(i))
        layout.addWidget(bt_remover)

        return linha

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
        self._pintar_cliente()

    def gerar_qrcode_pix(self):

        valor = _texto_para_valor(self.campo_valor.text())
        if valor <= EPSILON:
            self.lbl_qrcode.setText("")
            self.lbl_pix_info.setText("Informe o valor pra gerar o QR Code.")
            return

        self.lbl_qrcode.setText("Gerando QR Code...")
        self.lbl_pix_info.setText("")

        rodar_em_thread(
            self,
            _gerar_qrcode_pix_dados,
            valor,
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
            pixmap.scaled(170, 170, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self.lbl_pix_info.setText(texto_info)

    def _ao_qrcode_pix_erro(self, erro):
        self.lbl_qrcode.setText("QR Code indisponível")
        self.lbl_pix_info.setText(f"Não foi possível gerar o QR Code.\n{erro}")

    # ======================================
    # CONFIRMACAO
    # ======================================

    def confirmar(self):

        if not self.quitado():
            self._avisar(f"Ainda falta R$ {_fmt(self.falta())} pra fechar a venda.")
            return

        formas = [p["forma"] for p in self.pagamentos]

        if "PRAZO" in formas and self.cliente_id is None:
            QMessageBox.warning(self, "Atenção", "Selecione o cliente do crediário (F2).")
            return

        # venda zerada (desconto de 100%) nao tem pagamento lancado
        self.forma_pagamento = (
            self.pagamentos[0]["forma"] if self.pagamentos else "DINHEIRO"
        )

        if len(self.pagamentos) > 1:
            self.forma_pagamento_2 = self.pagamentos[1]["forma"]
            self.valor_forma_2 = self.pagamentos[1]["valor"]
        else:
            self.forma_pagamento_2 = None
            self.valor_forma_2 = 0.0

        self.accept()
