from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from services.movimento_fiado_service import (
    saldo_cliente,
    listar_movimentos_cliente,
    registrar_pagamento,
)

FORMAS_PAGAMENTO = [
    ("Dinheiro", "DINHEIRO"),
    ("PIX", "PIX"),
    ("Débito", "DEBITO"),
    ("Crédito", "CREDITO"),
]


class RegistrarPagamentoDialog(QDialog):

    def __init__(self, cliente, saldo_devedor, parent=None):

        super().__init__(parent)

        self.cliente = cliente
        self.forma_pagamento = "DINHEIRO"

        self.setWindowTitle("Registrar Pagamento")
        self.setFixedSize(400, 420)
        self.setStyleSheet("background:white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        titulo = QLabel("Registrar Pagamento")
        titulo.setStyleSheet(
            "background:transparent; font-size:17px; "
            "font-weight:bold; color:#202225;"
        )

        subtitulo = QLabel(
            f"Saldo devedor de {cliente['nome']}: "
            f"R$ {saldo_devedor:.2f}"
        )
        subtitulo.setWordWrap(True)
        subtitulo.setStyleSheet(
            "background:transparent; font-size:12px; color:gray;"
        )

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(6)

        lbl_valor_titulo = QLabel("VALOR A PAGAR (R$)")
        lbl_valor_titulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        self.valor = QLineEdit()
        self.valor.setText(f"{saldo_devedor:.2f}")
        self.valor.setAlignment(Qt.AlignCenter)
        self.valor.setStyleSheet("""
            QLineEdit {
                font-size:32px;
                font-weight:bold;
                color:#2E7D32;
                border:none;
                border-bottom:2px solid #e0e0e0;
                padding:6px 0;
            }
        """)

        layout.addWidget(lbl_valor_titulo)
        layout.addWidget(self.valor)

        lbl_forma_titulo = QLabel("FORMA DE PAGAMENTO")
        lbl_forma_titulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        layout.addWidget(lbl_forma_titulo)

        formas_layout = QGridLayout()
        formas_layout.setSpacing(8)

        self.botoes_forma = {}

        for indice, (rotulo, valor) in enumerate(FORMAS_PAGAMENTO):

            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setAutoDefault(False)
            bt.setMinimumHeight(46)
            bt.clicked.connect(
                lambda checked, v=valor: self.selecionar_forma(v)
            )

            self.botoes_forma[valor] = bt
            formas_layout.addWidget(bt, indice // 2, indice % 2)

        layout.addLayout(formas_layout)

        layout.addStretch()

        botoes = QHBoxLayout()

        bt_cancelar = QPushButton("Cancelar")
        bt_cancelar.setMinimumHeight(46)
        bt_cancelar.setAutoDefault(False)
        bt_cancelar.setStyleSheet("""
            QPushButton {
                background:white;
                color:#202225;
                border:1px solid #cccccc;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#e8e8e8;
            }
        """)
        bt_cancelar.clicked.connect(self.reject)

        self.bt_confirmar = QPushButton("Confirmar")
        self.bt_confirmar.setMinimumHeight(46)
        self.bt_confirmar.setAutoDefault(False)
        self.bt_confirmar.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                color:white;
                font-weight:bold;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
        """)
        self.bt_confirmar.clicked.connect(self.confirmar)

        botoes.addWidget(bt_cancelar)
        botoes.addWidget(self.bt_confirmar)

        layout.addLayout(botoes)

        self.selecionar_forma("DINHEIRO")

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

    def confirmar(self):

        try:
            valor = float(self.valor.text().replace(",", "."))
        except ValueError:
            QMessageBox.warning(
                self, "Atenção", "Informe um valor válido."
            )
            return

        if valor <= 0:
            QMessageBox.warning(
                self, "Atenção", "Informe um valor maior que zero."
            )
            return

        response = registrar_pagamento(
            self.cliente["id"],
            valor,
            self.forma_pagamento,
        )

        if response.status_code in (200, 201):
            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))


class FichaClienteDialog(QDialog):

    def __init__(self, cliente, parent=None):

        super().__init__(parent)

        self.cliente = cliente

        self.setWindowTitle(f"Ficha - {cliente['nome']}")
        self.resize(620, 640)
        self.setStyleSheet("background:#f4f5f7;")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QFrame()
        cabecalho.setStyleSheet("background:#202225;")

        cab_layout = QVBoxLayout(cabecalho)
        cab_layout.setContentsMargins(24, 20, 24, 20)
        cab_layout.setSpacing(4)

        self.lbl_titulo = QLabel(cliente["nome"])
        self.lbl_titulo.setStyleSheet(
            "background:transparent; color:white; "
            "font-size:20px; font-weight:bold;"
        )

        self.lbl_subtitulo = QLabel()
        self.lbl_subtitulo.setWordWrap(True)
        self.lbl_subtitulo.setStyleSheet(
            "background:transparent; color:#aaaaaa; font-size:12px;"
        )
        self._atualizar_cabecalho(cliente)

        cab_layout.addWidget(self.lbl_titulo)
        cab_layout.addWidget(self.lbl_subtitulo)

        raiz.addWidget(cabecalho)

        # ======================
        # CORPO
        # ======================

        corpo = QVBoxLayout()
        corpo.setContentsMargins(24, 20, 24, 20)
        corpo.setSpacing(16)

        saldo_frame = QFrame()
        saldo_frame.setStyleSheet(
            "background:white; border-radius:12px;"
        )

        saldo_layout = QHBoxLayout(saldo_frame)
        saldo_layout.setContentsMargins(20, 18, 20, 18)

        col_saldo = QVBoxLayout()
        col_saldo.setSpacing(2)

        lbl_saldo_titulo = QLabel("SALDO DEVEDOR (FIADO)")
        lbl_saldo_titulo.setStyleSheet(
            "background:transparent; border:none; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        self.lbl_saldo_valor = QLabel("R$ 0,00")
        self.lbl_saldo_valor.setStyleSheet(
            "background:transparent; border:none; font-size:28px; "
            "font-weight:bold; color:#C62828;"
        )

        col_saldo.addWidget(lbl_saldo_titulo)
        col_saldo.addWidget(self.lbl_saldo_valor)

        saldo_layout.addLayout(col_saldo)
        saldo_layout.addStretch()

        self.bt_pagar = QPushButton("Registrar Pagamento")
        self.bt_pagar.setMinimumHeight(46)
        self.bt_pagar.setAutoDefault(False)
        self.bt_pagar.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                color:white;
                font-weight:bold;
                border-radius:10px;
                padding:0 18px;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
        """)
        self.bt_pagar.clicked.connect(self.registrar_pagamento)

        saldo_layout.addWidget(self.bt_pagar)

        corpo.addWidget(saldo_frame)

        lbl_historico_titulo = QLabel("HISTÓRICO DO FIADO")
        lbl_historico_titulo.setStyleSheet(
            "font-size:11px; font-weight:bold; color:gray;"
        )

        corpo.addWidget(lbl_historico_titulo)

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(4)
        self.tabela.setHorizontalHeaderLabels(
            ["Data/Hora", "Tipo", "Valor", "Descrição"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tabela.setSelectionMode(QTableWidget.NoSelection)
        self.tabela.setFocusPolicy(Qt.NoFocus)
        self.tabela.setStyleSheet("""
            QTableWidget {
                background:white;
                alternate-background-color:#f8f9fb;
                border:1px solid #e0e0e0;
                border-radius:10px;
                gridline-color:#eeeeee;
                color:#202225;
            }
            QTableWidget::item {
                color:#202225;
                background:transparent;
            }
            QHeaderView::section {
                background:#f4f5f7;
                color:#555;
                padding:6px;
                border:none;
                border-bottom:1px solid #e0e0e0;
                font-weight:bold;
            }
        """)

        corpo.addWidget(self.tabela, stretch=1)

        raiz.addLayout(corpo)

        # ======================
        # RODAPÉ
        # ======================

        rodape = QFrame()
        rodape.setStyleSheet(
            "background:#f4f5f7; border-top:1px solid #e0e0e0;"
        )

        rodape_layout = QHBoxLayout(rodape)
        rodape_layout.setContentsMargins(24, 14, 24, 14)

        bt_editar = QPushButton("Editar")
        bt_editar.setMinimumHeight(42)
        bt_editar.setAutoDefault(False)
        bt_editar.setStyleSheet("""
            QPushButton {
                background:#1565C0;
                color:white;
                font-weight:bold;
                border-radius:10px;
                padding:0 20px;
            }
            QPushButton:hover {
                background:#0D47A1;
            }
        """)
        bt_editar.clicked.connect(self.editar_cliente)

        bt_excluir = QPushButton("Excluir")
        bt_excluir.setMinimumHeight(42)
        bt_excluir.setAutoDefault(False)
        bt_excluir.setStyleSheet("""
            QPushButton {
                background:#C62828;
                color:white;
                font-weight:bold;
                border-radius:10px;
                padding:0 20px;
            }
            QPushButton:hover {
                background:#B71C1C;
            }
        """)
        bt_excluir.clicked.connect(self.excluir_cliente_atual)

        bt_fechar = QPushButton("Fechar")
        bt_fechar.setMinimumHeight(42)
        bt_fechar.setAutoDefault(False)
        bt_fechar.setStyleSheet("""
            QPushButton {
                background:white;
                color:#202225;
                border:1px solid #cccccc;
                border-radius:10px;
                padding:0 24px;
            }
            QPushButton:hover {
                background:#e8e8e8;
            }
        """)
        bt_fechar.clicked.connect(self.accept)

        rodape_layout.addWidget(bt_editar)
        rodape_layout.addWidget(bt_excluir)
        rodape_layout.addStretch()
        rodape_layout.addWidget(bt_fechar)

        raiz.addWidget(rodape)

        self.carregar()

    # ======================================

    def _atualizar_cabecalho(self, cliente):

        self.lbl_titulo.setText(cliente["nome"])

        detalhes = " · ".join(
            filter(
                None,
                [
                    cliente.get("telefone"),
                    cliente.get("cpf_cnpj"),
                    cliente.get("endereco"),
                ],
            )
        ) or "Sem dados de contato"

        self.lbl_subtitulo.setText(detalhes)

    def editar_cliente(self):

        from telas.cadastro_cliente import CadastroClienteDialog

        dialogo = CadastroClienteDialog(self.cliente, parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        if dialogo.cliente_salvo:
            self.cliente = dialogo.cliente_salvo
            self._atualizar_cabecalho(self.cliente)

    def excluir_cliente_atual(self):

        from services.cliente_service import excluir_cliente

        resposta = QMessageBox.question(
            self,
            "Excluir Cliente",
            f"Deseja desativar o cliente\n\n{self.cliente['nome']} ?"
        )

        if resposta != QMessageBox.Yes:
            return

        response = excluir_cliente(self.cliente["id"])

        if response.status_code == 200:
            self.accept()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def carregar(self):

        saldo = saldo_cliente(self.cliente["id"])

        self.lbl_saldo_valor.setText(f"R$ {saldo:.2f}")
        self.lbl_saldo_valor.setStyleSheet(
            "background:transparent; border:none; font-size:28px; "
            "font-weight:bold; "
            f"color:{'#C62828' if saldo > 0 else '#2E7D32'};"
        )

        self.bt_pagar.setEnabled(saldo > 0)

        movimentos = listar_movimentos_cliente(self.cliente["id"])

        movimentos = sorted(
            movimentos,
            key=lambda m: m.get("data", ""),
            reverse=True,
        )

        self.tabela.setRowCount(len(movimentos))

        for linha, mov in enumerate(movimentos):

            data = str(mov.get("data", ""))
            if "T" in data:
                data = data.replace("T", " ")

            tipo = mov.get("tipo", "")

            valor = float(mov.get("valor", 0) or 0)
            texto_valor = (
                f"+ R$ {valor:.2f}"
                if tipo == "COMPRA"
                else f"- R$ {valor:.2f}"
            )

            self.tabela.setItem(
                linha, 0, QTableWidgetItem(data[:19])
            )
            self.tabela.setItem(linha, 1, QTableWidgetItem(tipo))
            self.tabela.setItem(
                linha, 2, QTableWidgetItem(texto_valor)
            )
            self.tabela.setItem(
                linha,
                3,
                QTableWidgetItem(mov.get("descricao") or ""),
            )

    def registrar_pagamento(self):

        saldo = saldo_cliente(self.cliente["id"])

        if saldo <= 0:
            QMessageBox.information(
                self,
                "Fiado",
                "Este cliente não tem saldo devedor.",
            )
            return

        dialogo = RegistrarPagamentoDialog(
            self.cliente,
            saldo,
            parent=self,
        )

        if dialogo.exec() != QDialog.Accepted:
            return

        self.carregar()
