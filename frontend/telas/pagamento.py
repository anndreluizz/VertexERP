from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QCompleter,
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QRadioButton,
    QLineEdit,
    QButtonGroup,
    QMessageBox,
    QWidget,
)

from services.cliente_service import listar_clientes, cadastrar_cliente
from services.configuracao_service import buscar_configuracoes
from services.pix_service import gerar_payload_pix, gerar_qrcode_pixmap
from telas.cadastro_cliente import CadastroClienteWindow


class PagamentoWindow(QDialog):

    def __init__(self, total):
        super().__init__()

        self.total = total
        self.forma_pagamento = "DINHEIRO"
        self.cliente_id = None
        self.cliente_nome = ""
        self.valor_entrada = 0.0

        self.setWindowTitle("Finalizar Venda")
        self.setMinimumWidth(520)

        self._pix_gerado = False

        layout = QVBoxLayout(self)

        titulo = QLabel("FINALIZAR VENDA")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("""
            font-size:22px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        # ===========================
        # TOTAL
        # ===========================

        self.lbl_total = QLabel(
            f"TOTAL: R$ {total:.2f}"
        )

        self.lbl_total.setAlignment(Qt.AlignCenter)

        self.lbl_total.setStyleSheet("""
            font-size:30px;
            color:#1565C0;
            font-weight:bold;
        """)

        layout.addWidget(self.lbl_total)

        # ===========================
        # FORMAS DE PAGAMENTO
        # ===========================

        self.dinheiro = QRadioButton("1 — Dinheiro")
        self.pix = QRadioButton("2 — PIX")
        self.debito = QRadioButton("3 — Cartão de Débito")
        self.credito = QRadioButton("4 — Cartão de Crédito")
        self.prazo = QRadioButton("5 — Prazo (Fiado)")

        self.dinheiro.setChecked(True)

        grupo = QButtonGroup(self)

        grupo.addButton(self.dinheiro)
        grupo.addButton(self.pix)
        grupo.addButton(self.debito)
        grupo.addButton(self.credito)
        grupo.addButton(self.prazo)

        layout.addWidget(self.dinheiro)
        layout.addWidget(self.pix)
        layout.addWidget(self.debito)
        layout.addWidget(self.credito)
        layout.addWidget(self.prazo)

        # Atalho explícito em vez de mnemônico "&" — mais confiável e não
        # depende do estilo/skin do Windows revelar o sublinhado do Alt.
        QShortcut(QKeySequence("Alt+1"), self, self.dinheiro.click)
        QShortcut(QKeySequence("Alt+2"), self, self.pix.click)
        QShortcut(QKeySequence("Alt+3"), self, self.debito.click)
        QShortcut(QKeySequence("Alt+4"), self, self.credito.click)
        QShortcut(QKeySequence("Alt+5"), self, self.prazo.click)

        # ===========================
        # PIX (QR Code + copia e cola)
        # ===========================

        self.pix_widget = QWidget()

        pix_layout = QVBoxLayout(self.pix_widget)
        pix_layout.setContentsMargins(0, 8, 0, 8)

        self.pix_qr_label = QLabel()
        self.pix_qr_label.setAlignment(Qt.AlignCenter)
        pix_layout.addWidget(self.pix_qr_label)

        self.pix_copia_cola = QLineEdit()
        self.pix_copia_cola.setReadOnly(True)
        pix_layout.addWidget(self.pix_copia_cola)

        layout.addWidget(self.pix_widget)

        self.pix_widget.setVisible(False)
        self.pix.toggled.connect(self._alternar_pix)

        # ===========================
        # CLIENTE (obrigatório para Prazo/fiado)
        # ===========================

        self.cliente_widget = QWidget()

        cliente_layout = QHBoxLayout(self.cliente_widget)
        cliente_layout.setContentsMargins(0, 0, 0, 0)

        # Busca inline (digitar já filtra e sugere) em vez de abrir uma
        # janela de pesquisa separada — mais rápido pro fluxo do fiado,
        # que é o diferencial do sistema.
        self.cliente_label = QLineEdit()
        self.cliente_label.setPlaceholderText(
            "Digite o nome do cliente (obrigatório para venda a prazo)"
        )

        self._mapa_clientes_por_texto = {}
        self._carregar_completer_clientes()

        self.cliente_label.textChanged.connect(self._resolver_cliente_digitado)

        self.bt_novo_cliente = QPushButton("+ Novo Cliente")
        self.bt_novo_cliente.clicked.connect(self.novo_cliente)

        cliente_layout.addWidget(self.cliente_label)
        cliente_layout.addWidget(self.bt_novo_cliente)

        layout.addWidget(self.cliente_widget)

        # ===========================
        # ENTRADA (pagamento parcial no ato, opcional)
        # ===========================

        self.entrada_widget = QWidget()

        entrada_layout = QHBoxLayout(self.entrada_widget)
        entrada_layout.setContentsMargins(0, 0, 0, 0)

        entrada_layout.addWidget(QLabel("Entrada (opcional):"))

        self.entrada_input = QLineEdit()
        self.entrada_input.setPlaceholderText(
            "Valor pago agora — o restante fica no fiado"
        )

        entrada_layout.addWidget(self.entrada_input)

        layout.addWidget(self.entrada_widget)

        self.cliente_widget.setVisible(False)
        self.entrada_widget.setVisible(False)
        self.prazo.toggled.connect(self.cliente_widget.setVisible)
        self.prazo.toggled.connect(self.entrada_widget.setVisible)

        # ===========================
        # VALOR RECEBIDO (só faz sentido em Dinheiro)
        # ===========================

        self.dinheiro_widget = QWidget()

        dinheiro_layout = QVBoxLayout(self.dinheiro_widget)
        dinheiro_layout.setContentsMargins(0, 8, 0, 0)

        self.recebido = QLineEdit()
        self.recebido.setPlaceholderText("Valor Recebido")

        dinheiro_layout.addWidget(self.recebido)

        # Valores rápidos: cédulas comuns (só as que fazem sentido pra
        # esse total) + o valor exato, pra economizar digitação nas
        # vendas mais comuns.
        valores_rapidos = QHBoxLayout()

        for cedula in (10, 20, 50, 100, 200):
            if cedula < total:
                continue

            bt_valor = QPushButton(f"R$ {cedula}")
            bt_valor.clicked.connect(
                lambda _, v=cedula: self._preencher_valor_recebido(v)
            )
            valores_rapidos.addWidget(bt_valor)

        bt_exato = QPushButton("Valor Exato")
        bt_exato.clicked.connect(
            lambda: self._preencher_valor_recebido(total)
        )
        valores_rapidos.addWidget(bt_exato)

        dinheiro_layout.addLayout(valores_rapidos)

        self.troco = QLabel("Troco: R$ 0,00")

        self.troco.setStyleSheet("""
            font-size:18px;
            font-weight:bold;
        """)

        dinheiro_layout.addWidget(self.troco)

        layout.addWidget(self.dinheiro_widget)

        self.dinheiro.toggled.connect(self.dinheiro_widget.setVisible)

        self.recebido.textChanged.connect(
            self.calcular_troco
        )

        # ===========================
        # BOTÕES
        # ===========================

        botoes = QHBoxLayout()

        self.bt_cancelar = QPushButton("Cancelar")
        self.bt_confirmar = QPushButton("Confirmar Venda (Enter)")

        # Enter confirma a venda de qualquer campo focado (recebido,
        # entrada, etc.), sem precisar clicar no botão.
        self.bt_confirmar.setDefault(True)
        self.bt_confirmar.setAutoDefault(True)
        self.bt_cancelar.setAutoDefault(False)

        botoes.addWidget(self.bt_cancelar)
        botoes.addWidget(self.bt_confirmar)

        layout.addStretch()
        layout.addLayout(botoes)

        self.bt_cancelar.clicked.connect(self.reject)
        self.bt_confirmar.clicked.connect(self.confirmar)

    # ======================================

    def _alternar_pix(self, marcado):

        self.pix_widget.setVisible(marcado)

        if marcado and not self._pix_gerado:

            config = buscar_configuracoes()

            if not config.get("pix_chave"):
                QMessageBox.warning(
                    self,
                    "PIX não configurado",
                    "Cadastre a chave PIX da loja em "
                    "Configurações > PIX antes de usar essa forma "
                    "de pagamento."
                )
                self.pix_widget.setVisible(False)
                return

            payload = gerar_payload_pix(
                self.total,
                config["pix_chave"],
                config.get("pix_nome") or "",
                config.get("pix_cidade") or "",
            )

            pixmap = gerar_qrcode_pixmap(payload)

            self.pix_qr_label.setPixmap(
                pixmap.scaled(
                    200,
                    200,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )

            self.pix_copia_cola.setText(payload)

            self._pix_gerado = True

    # ======================================

    def calcular_troco(self):

        try:
            recebido = float(
                self.recebido.text().replace(",", ".")
            )
        except:
            recebido = 0

        troco = recebido - self.total

        if troco < 0:
            troco = 0

        self.troco.setText(
            f"Troco: R$ {troco:.2f}"
        )

    # ======================================

    def _preencher_valor_recebido(self, valor):
        self.recebido.setText(f"{valor:.2f}")
        self.recebido.setFocus()

    # ======================================

    def confirmar(self):

        if self.dinheiro.isChecked():

            self.forma_pagamento = "DINHEIRO"

            try:
                recebido = float(
                    self.recebido.text().replace(",", ".")
                )
            except:
                QMessageBox.warning(
                    self,
                    "Atenção",
                    "Informe o valor recebido."
                )
                return

            if recebido < self.total:

                QMessageBox.warning(
                    self,
                    "Atenção",
                    "O valor recebido é menor que o total."
                )
                return

        elif self.pix.isChecked():

            self.forma_pagamento = "PIX"

        elif self.debito.isChecked():

            self.forma_pagamento = "DEBITO"

        elif self.credito.isChecked():

            self.forma_pagamento = "CREDITO"

        else:

            self.forma_pagamento = "PRAZO"

            if self.cliente_id is None:

                QMessageBox.warning(
                    self,
                    "Atenção",
                    "Selecione o cliente para venda a prazo (fiado)."
                )
                return

            texto_entrada = self.entrada_input.text().strip()

            if texto_entrada:

                try:
                    entrada = float(texto_entrada.replace(",", "."))
                except ValueError:
                    QMessageBox.warning(
                        self,
                        "Atenção",
                        "Valor de entrada inválido."
                    )
                    return

                if entrada < 0 or entrada > self.total:

                    QMessageBox.warning(
                        self,
                        "Atenção",
                        "A entrada não pode ser negativa nem maior que o total."
                    )
                    return

                self.valor_entrada = entrada

        self.accept()

    # ======================================

    def _carregar_completer_clientes(self):

        clientes = listar_clientes()

        self._mapa_clientes_por_texto = {}

        for cliente in clientes:
            texto = cliente["nome"]

            if cliente.get("cpf_cnpj"):
                texto = f"{cliente['nome']} — {cliente['cpf_cnpj']}"

            self._mapa_clientes_por_texto[texto] = cliente

        completer = QCompleter(list(self._mapa_clientes_por_texto.keys()), self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.activated.connect(self._selecionar_cliente_do_completer)

        self.cliente_label.setCompleter(completer)

    def _selecionar_cliente_do_completer(self, texto):
        self._aplicar_cliente_resolvido(texto)

    def _resolver_cliente_digitado(self, texto):
        # Cobre o caso de colar/digitar o texto exato sem usar o dropdown
        # do completer — se não bater com nenhum cliente conhecido, limpa
        # o id pra não deixar um cliente antigo selecionado por engano.
        self._aplicar_cliente_resolvido(texto)

    def _aplicar_cliente_resolvido(self, texto):
        cliente = self._mapa_clientes_por_texto.get(texto)
        self.cliente_id = cliente["id"] if cliente else None
        self.cliente_nome = cliente["nome"] if cliente else ""

    # ======================================

    def novo_cliente(self):

        tela = CadastroClienteWindow()

        if tela.exec() != QDialog.Accepted:
            return

        if not tela.dados["nome"].strip():

            QMessageBox.warning(
                self,
                "Atenção",
                "Informe o nome do cliente."
            )
            return

        response = cadastrar_cliente(tela.dados)

        if response.status_code not in (200, 201):

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", erro)
            return

        cliente = response.json()

        texto = cliente["nome"]

        if cliente.get("cpf_cnpj"):
            texto = f"{cliente['nome']} — {cliente['cpf_cnpj']}"

        self._mapa_clientes_por_texto[texto] = cliente

        self.cliente_id = cliente["id"]
        self.cliente_nome = cliente["nome"]

        self.cliente_label.setText(texto)