from io import BytesIO

import qrcode
from PySide6.QtCore import Qt
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
    QCheckBox,
    QMessageBox,
)

from services.api import configuracoes
from services.pix_utils import montar_payload_pix
from telas.selecionar_cliente import SelecionarClienteDialog

FORMAS = [
    ("Dinheiro", "DINHEIRO"),
    ("Débito", "DEBITO"),
    ("Crédito", "CREDITO"),
    ("PIX", "PIX"),
    ("A Prazo", "PRAZO"),
]

NOMES_FORMA = {valor: rotulo for rotulo, valor in FORMAS}

VALORES_RAPIDOS = [1, 2, 5, 10, 20, 50, 100]


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

        self.setWindowTitle("Pagamento")
        self.setFixedSize(980, 720)
        self.setStyleSheet("background:white;")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QFrame()
        cabecalho.setStyleSheet("background:#202225;")
        cabecalho.setFixedHeight(64)

        cab_layout = QHBoxLayout(cabecalho)
        cab_layout.setContentsMargins(24, 0, 24, 0)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("PAGAMENTO")
        titulo.setStyleSheet(
            "background:transparent; color:white; "
            "font-size:16px; font-weight:bold;"
        )

        subtitulo = QLabel("Selecione o método e finalize")
        subtitulo.setStyleSheet(
            "background:transparent; color:#aaaaaa; font-size:11px;"
        )

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        self.bt_cancelar = QPushButton("✕ Cancelar Venda")
        self.bt_cancelar.setAutoDefault(False)
        self.bt_cancelar.setStyleSheet("""
            QPushButton {
                background:#3a3d42;
                color:white;
                border-radius:8px;
                padding:8px 14px;
            }
            QPushButton:hover {
                background:#4a4e54;
            }
        """)
        self.bt_cancelar.clicked.connect(self.reject)

        cab_layout.addLayout(col_titulo)
        cab_layout.addStretch()
        cab_layout.addWidget(self.bt_cancelar)

        raiz.addWidget(cabecalho)

        # ======================
        # CORPO (2 colunas)
        # ======================

        corpo = QHBoxLayout()
        corpo.setContentsMargins(0, 0, 0, 0)
        corpo.setSpacing(0)

        # ---- coluna esquerda: resumo ----

        esquerda = QFrame()
        esquerda.setFixedWidth(320)
        esquerda.setStyleSheet(
            "background:#f4f5f7; border-right:1px solid #e0e0e0;"
        )

        esq_layout = QVBoxLayout(esquerda)
        esq_layout.setContentsMargins(24, 24, 24, 24)
        esq_layout.setSpacing(4)

        lbl_total_titulo = QLabel("TOTAL DA FATURA")
        lbl_total_titulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        self.lbl_total = QLabel(f"R$ {total:.2f}")
        self.lbl_total.setStyleSheet(
            "background:transparent; font-size:34px; "
            "font-weight:bold; color:#2E7D32;"
        )

        esq_layout.addWidget(lbl_total_titulo)
        esq_layout.addWidget(self.lbl_total)
        esq_layout.addSpacing(16)

        lbl_resumo_titulo = QLabel(
            f"RESUMO · {len(self.itens)} ITENS"
        )
        lbl_resumo_titulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        esq_layout.addWidget(lbl_resumo_titulo)

        for item in self.itens:

            linha_item = QHBoxLayout()

            nome = QLabel(item["nome"])
            nome.setStyleSheet(
                "background:transparent; font-size:12px; color:#202225;"
            )

            subtotal = item["preco"] * item["quantidade"]

            valor = QLabel(f"R$ {subtotal:.2f}")
            valor.setAlignment(Qt.AlignRight)
            valor.setStyleSheet(
                "background:transparent; font-size:12px; color:#202225;"
            )

            linha_item.addWidget(nome)
            linha_item.addWidget(valor)

            esq_layout.addLayout(linha_item)

        esq_layout.addStretch()

        lbl_saldo_titulo = QLabel("SALDO EM ABERTO")
        lbl_saldo_titulo.setStyleSheet(
            "background:transparent; font-size:11px; color:gray;"
        )

        self.lbl_saldo = QLabel(f"R$ {total:.2f}")
        self.lbl_saldo.setStyleSheet(
            "background:transparent; font-size:18px; "
            "font-weight:bold; color:#2E7D32;"
        )

        esq_layout.addWidget(lbl_saldo_titulo)
        esq_layout.addWidget(self.lbl_saldo)

        corpo.addWidget(esquerda)

        # ---- coluna direita: formas de pagamento ----

        direita = QFrame()
        direita.setStyleSheet("background:white;")

        dir_layout = QVBoxLayout(direita)
        dir_layout.setContentsMargins(24, 24, 24, 24)
        dir_layout.setSpacing(18)

        formas_layout = QHBoxLayout()
        formas_layout.setSpacing(10)

        self.botoes_forma = {}

        for rotulo, valor in FORMAS:

            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setMinimumHeight(64)
            bt.clicked.connect(
                lambda checked, v=valor: self.selecionar_forma(v)
            )

            self.botoes_forma[valor] = bt
            formas_layout.addWidget(bt)

        dir_layout.addLayout(formas_layout)

        # ---- dividir pagamento (2ª forma) ----

        self.check_dividir = QCheckBox(
            "Dividir com uma 2ª forma de pagamento"
        )
        self.check_dividir.setStyleSheet(
            "background:transparent; font-size:12px; color:#202225;"
        )
        self.check_dividir.stateChanged.connect(
            self.alternar_divisao
        )

        dir_layout.addWidget(self.check_dividir)

        self.bloco_divisao = QFrame()
        self.bloco_divisao.setStyleSheet(
            "background:#f4f5f7; border-radius:8px;"
        )
        self.bloco_divisao.setVisible(False)

        divisao_layout = QVBoxLayout(self.bloco_divisao)
        divisao_layout.setContentsMargins(14, 12, 14, 12)
        divisao_layout.setSpacing(8)

        lbl_2forma_titulo = QLabel("2ª FORMA DE PAGAMENTO")
        lbl_2forma_titulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )
        divisao_layout.addWidget(lbl_2forma_titulo)

        formas_2_layout = QHBoxLayout()
        formas_2_layout.setSpacing(6)

        self.botoes_forma_2 = {}

        for rotulo, valor in FORMAS:

            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setMinimumHeight(40)
            bt.setAutoDefault(False)
            bt.clicked.connect(
                lambda checked, v=valor: self.selecionar_forma_2(v)
            )

            self.botoes_forma_2[valor] = bt
            formas_2_layout.addWidget(bt)

        divisao_layout.addLayout(formas_2_layout)

        lbl_valor_2_titulo = QLabel("VALOR NESTA FORMA (R$)")
        lbl_valor_2_titulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )
        divisao_layout.addWidget(lbl_valor_2_titulo)

        self.valor_2 = QLineEdit()
        self.valor_2.setPlaceholderText("0,00")
        self.valor_2.setStyleSheet("""
            QLineEdit {
                background:white;
                font-size:18px;
                font-weight:bold;
                color:#202225;
                border:1px solid #cccccc;
                border-radius:8px;
                padding:6px 10px;
            }
        """)
        self.valor_2.textChanged.connect(self.atualizar_valor_principal)
        divisao_layout.addWidget(self.valor_2)

        self.lbl_valor_principal = QLabel()
        self.lbl_valor_principal.setStyleSheet(
            "background:transparent; font-size:12px; "
            "font-weight:bold; color:#2E7D32;"
        )
        divisao_layout.addWidget(self.lbl_valor_principal)

        dir_layout.addWidget(self.bloco_divisao)

        # ---- entrada de valor (dinheiro) ----

        self.bloco_dinheiro = QFrame()

        bloco_layout = QVBoxLayout(self.bloco_dinheiro)
        bloco_layout.setSpacing(10)

        lbl_entrada_titulo = QLabel("ENTRADA DE VALOR")
        lbl_entrada_titulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        self.recebido = QLineEdit()
        self.recebido.setPlaceholderText("R$ 0,00")
        self.recebido.setAlignment(Qt.AlignRight)
        self.recebido.setStyleSheet("""
            QLineEdit {
                font-size:32px;
                font-weight:bold;
                color:#2E7D32;
                border:none;
                border-bottom:2px solid #e0e0e0;
                padding:6px 0;
            }
        """)
        self.recebido.textChanged.connect(self.calcular_troco)

        bloco_layout.addWidget(lbl_entrada_titulo)
        bloco_layout.addWidget(self.recebido)

        valores_layout = QGridLayout()
        valores_layout.setSpacing(8)

        for indice, valor in enumerate(VALORES_RAPIDOS):

            bt = QPushButton(f"+R$ {valor}")
            bt.setMinimumHeight(36)
            bt.setStyleSheet("""
                QPushButton {
                    background:#f4f5f7;
                    color:#202225;
                    border-radius:6px;
                }
                QPushButton:hover {
                    background:#e8e8e8;
                }
            """)
            bt.clicked.connect(
                lambda checked, v=valor: self.adicionar_valor(v)
            )

            valores_layout.addWidget(bt, indice // 4, indice % 4)

        bloco_layout.addLayout(valores_layout)

        self.troco = QLabel("Troco: R$ 0,00")
        self.troco.setStyleSheet(
            "background:transparent; font-size:14px; "
            "font-weight:bold; color:#202225;"
        )

        bloco_layout.addWidget(self.troco)

        dir_layout.addWidget(self.bloco_dinheiro)

        # ---- QR Code (pix) ----

        self.bloco_pix = QFrame()

        pix_layout = QVBoxLayout(self.bloco_pix)
        pix_layout.setSpacing(10)
        pix_layout.setAlignment(Qt.AlignHCenter)

        self.lbl_qrcode = QLabel()
        self.lbl_qrcode.setAlignment(Qt.AlignCenter)
        self.lbl_qrcode.setFixedSize(220, 220)
        self.lbl_qrcode.setStyleSheet(
            "background:transparent; color:#202225; font-size:12px;"
        )

        self.lbl_pix_info = QLabel()
        self.lbl_pix_info.setAlignment(Qt.AlignCenter)
        self.lbl_pix_info.setWordWrap(True)
        self.lbl_pix_info.setStyleSheet(
            "background:transparent; font-size:11px; color:gray;"
        )

        pix_layout.addWidget(self.lbl_qrcode, alignment=Qt.AlignHCenter)
        pix_layout.addWidget(self.lbl_pix_info)

        dir_layout.addWidget(self.bloco_pix)

        self.gerar_qrcode_pix()

        # ---- fiado (a prazo) ----

        self.bloco_prazo = QFrame()

        prazo_layout = QVBoxLayout(self.bloco_prazo)
        prazo_layout.setSpacing(10)

        lbl_prazo_titulo = QLabel("CLIENTE DO FIADO")
        lbl_prazo_titulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        self.lbl_cliente_selecionado = QLabel(
            self.cliente_nome or "Nenhum cliente selecionado"
        )
        self.lbl_cliente_selecionado.setWordWrap(True)
        self.lbl_cliente_selecionado.setStyleSheet(f"""
            background:transparent; font-size:16px; font-weight:bold;
            color: {"#2E7D32" if self.cliente_nome else "#C62828"};
        """)

        self.bt_selecionar_cliente = QPushButton(
            "Selecionar Cliente"
        )
        self.bt_selecionar_cliente.setMinimumHeight(44)
        self.bt_selecionar_cliente.setAutoDefault(False)
        self.bt_selecionar_cliente.setStyleSheet("""
            QPushButton {
                background:#f4f5f7;
                color:#202225;
                border-radius:8px;
                font-weight:bold;
            }
            QPushButton:hover {
                background:#e8e8e8;
            }
        """)
        self.bt_selecionar_cliente.clicked.connect(
            self.abrir_selecionar_cliente
        )

        prazo_layout.addWidget(lbl_prazo_titulo)
        prazo_layout.addWidget(self.lbl_cliente_selecionado)
        prazo_layout.addWidget(self.bt_selecionar_cliente)

        dir_layout.addWidget(self.bloco_prazo)

        dir_layout.addStretch()

        self.bt_confirmar = QPushButton("CONFIRMAR VENDA")
        self.bt_confirmar.setMinimumHeight(52)
        self.bt_confirmar.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                color:white;
                font-size:15px;
                font-weight:bold;
                border-radius:8px;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
        """)
        self.bt_confirmar.clicked.connect(self.confirmar)

        dir_layout.addWidget(self.bt_confirmar)

        corpo.addWidget(direita, stretch=1)

        raiz.addLayout(corpo)

        self.selecionar_forma("DINHEIRO")

    # ======================================

    def selecionar_forma(self, valor):

        self.forma_pagamento = valor

        for chave, botao in self.botoes_forma.items():

            selecionado = chave == valor

            botao.setChecked(selecionado)

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {"#2E7D32" if selecionado else "#f4f5f7"};
                    color: {"white" if selecionado else "#202225"};
                    border-radius: 8px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {"#1B5E20" if selecionado else "#e8e8e8"};
                }}
            """)

        self.bloco_dinheiro.setVisible(valor == "DINHEIRO")
        self.bloco_pix.setVisible(valor == "PIX")
        self.bloco_prazo.setVisible(valor == "PRAZO")

        if valor == "PRAZO" and self.cliente_id is None:
            self.abrir_selecionar_cliente()

        # a 2ª forma nao pode repetir a principal
        if valor in self.botoes_forma_2:
            self.botoes_forma_2[valor].setEnabled(False)
            if self.forma_pagamento_2 == valor:
                self.selecionar_forma_2(None)

        for chave, botao in self.botoes_forma_2.items():
            if chave != valor:
                botao.setEnabled(True)

        self.atualizar_valor_principal()

    def valor_principal(self):
        """Quanto da venda fica coberto pela forma de pagamento
        principal — o total inteiro, ou o total menos a 2ª forma
        quando o pagamento foi dividido."""

        if not self.dividir_pagamento:
            return self.total

        return max(0.0, self.total - self.valor_forma_2)

    def alternar_divisao(self, estado):

        self.dividir_pagamento = bool(estado)

        self.bloco_divisao.setVisible(self.dividir_pagamento)

        if not self.dividir_pagamento:
            self.selecionar_forma_2(None)
            self.valor_2.clear()

        self.atualizar_valor_principal()

    def selecionar_forma_2(self, valor):

        self.forma_pagamento_2 = valor

        for chave, botao in self.botoes_forma_2.items():

            selecionado = chave == valor

            botao.setChecked(selecionado)

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {"#C62828" if selecionado else "white"};
                    color: {"white" if selecionado else "#202225"};
                    border-radius: 6px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background: {"#8E1616" if selecionado else "#e8e8e8"};
                }}
            """)

        if valor == "PRAZO" and self.cliente_id is None:
            self.abrir_selecionar_cliente()

    def atualizar_valor_principal(self):

        try:
            self.valor_forma_2 = float(
                self.valor_2.text().replace(",", ".") or 0
            )
        except ValueError:
            self.valor_forma_2 = 0.0

        principal = self.valor_principal()
        nome_principal = NOMES_FORMA.get(
            self.forma_pagamento, self.forma_pagamento
        )

        self.lbl_valor_principal.setText(
            f"Nesta forma ({nome_principal}): R$ {principal:.2f}"
        )

        self.calcular_troco()

        if self.forma_pagamento == "PIX":
            self.gerar_qrcode_pix()

    def abrir_selecionar_cliente(self):

        dialogo = SelecionarClienteDialog(self)
        dialogo.cliente_selecionado.connect(self.definir_cliente)
        dialogo.exec()

    def definir_cliente(self, cliente):

        self.cliente_id = cliente["id"]
        self.cliente_nome = cliente["nome"]

        self.lbl_cliente_selecionado.setText(cliente["nome"])
        self.lbl_cliente_selecionado.setStyleSheet(
            "background:transparent; font-size:16px; "
            "font-weight:bold; color:#2E7D32;"
        )

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
                220,
                220,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

        self.lbl_pix_info.setText(
            f"Aponte a câmera do banco para pagar "
            f"R$ {self.valor_principal():.2f} via PIX para {chave}"
        )

    def adicionar_valor(self, valor):

        self.recebido_acumulado += valor

        self.recebido.setText(f"{self.recebido_acumulado:.2f}")

    def calcular_troco(self):

        try:
            recebido = float(
                self.recebido.text().replace(",", ".")
            )
        except ValueError:
            recebido = 0

        troco = recebido - self.valor_principal()

        if troco < 0:
            troco = 0

        self.troco.setText(f"Troco: R$ {troco:.2f}")

    # ======================================

    def confirmar(self):

        if self.dividir_pagamento:

            if not self.forma_pagamento_2:
                QMessageBox.warning(
                    self,
                    "Atenção",
                    "Escolha a 2ª forma de pagamento.",
                )
                return

            if not (0 < self.valor_forma_2 < self.total):
                QMessageBox.warning(
                    self,
                    "Atenção",
                    "O valor da 2ª forma precisa ser maior que "
                    "zero e menor que o total da venda.",
                )
                return

        else:
            self.forma_pagamento_2 = None
            self.valor_forma_2 = 0.0

        formas_da_venda = [self.forma_pagamento]
        if self.forma_pagamento_2:
            formas_da_venda.append(self.forma_pagamento_2)

        if self.forma_pagamento == "DINHEIRO":

            try:
                recebido = float(
                    self.recebido.text().replace(",", ".")
                )
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Atenção",
                    "Informe o valor recebido."
                )
                return

            if recebido < self.valor_principal():

                QMessageBox.warning(
                    self,
                    "Atenção",
                    "O valor recebido é menor que o valor "
                    "coberto por essa forma."
                )
                return

        if "PRAZO" in formas_da_venda and self.cliente_id is None:

            QMessageBox.warning(
                self,
                "Atenção",
                "Selecione o cliente do fiado antes de confirmar."
            )
            return

        self.accept()
