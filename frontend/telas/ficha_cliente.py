import base64
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtPrintSupport import QPrinter, QPrinterInfo
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from services.configuracao_service import (
    buscar_configuracoes,
    buscar_logo_bytes,
)
from services.fiado_service import (
    buscar_ficha,
    registrar_compra,
    registrar_pagamento,
)


class FichaClienteWindow(QDialog):

    def __init__(self, cliente):
        super().__init__()

        self.cliente = cliente

        self.setWindowTitle(f"Ficha de {cliente['nome']}")
        self.resize(700, 550)

        layout = QVBoxLayout(self)

        titulo = QLabel("FICHA DO CLIENTE (FIADO)")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:22px; font-weight:bold;")
        layout.addWidget(titulo)

        # ==========================================
        # DADOS DO CLIENTE
        # ==========================================
        info = QLabel(
            f"{cliente['nome']}  —  CPF: {cliente.get('cpf_cnpj') or '-'}"
            f"  —  Tel: {cliente.get('telefone') or '-'}"
        )
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("color:#9E9E9E; padding:4px;")
        layout.addWidget(info)

        self.saldo = QLabel("Saldo devedor: R$ 0,00")
        self.saldo.setAlignment(Qt.AlignCenter)
        self.saldo.setStyleSheet("font-size:26px; font-weight:bold;")
        layout.addWidget(self.saldo)

        # ==========================================
        # HISTÓRICO
        # ==========================================
        self.tabela = QTableWidget()
        self.tabela.setColumnCount(4)
        self.tabela.setHorizontalHeaderLabels(
            ["Data", "Tipo", "Descrição", "Valor"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.tabela)

        # ==========================================
        # LANÇAR COMPRA FIADO MANUAL
        # ==========================================
        layout.addWidget(QLabel("Lançar compra fiado"))

        compra_layout = QHBoxLayout()

        self.valor_compra = QLineEdit()
        self.valor_compra.setPlaceholderText("Valor da compra (R$)")

        self.descricao_compra = QLineEdit()
        self.descricao_compra.setPlaceholderText(
            "Produtos comprados / observação"
        )

        self.bt_lancar_compra = QPushButton("Lançar Compra")
        self.bt_lancar_compra.setStyleSheet("""
            QPushButton{
                background:#C62828;
                color:white;
                font-weight:bold;
                padding:6px 16px;
            }
            QPushButton:hover{
                background:#B71C1C;
            }
        """)

        compra_layout.addWidget(self.valor_compra)
        compra_layout.addWidget(self.descricao_compra)
        compra_layout.addWidget(self.bt_lancar_compra)

        layout.addLayout(compra_layout)

        # ==========================================
        # REGISTRAR PAGAMENTO
        # ==========================================
        layout.addWidget(QLabel("Registrar pagamento (abatimento)"))

        pagamento_layout = QHBoxLayout()

        self.valor_pagamento = QLineEdit()
        self.valor_pagamento.setPlaceholderText("Valor recebido (R$)")

        self.descricao_pagamento = QLineEdit()
        self.descricao_pagamento.setPlaceholderText(
            "Observação (opcional)"
        )

        self.bt_pagar = QPushButton("Registrar Pagamento")
        self.bt_pagar.setStyleSheet("""
            QPushButton{
                background:#2E7D32;
                color:white;
                font-weight:bold;
                padding:6px 16px;
            }
            QPushButton:hover{
                background:#1B5E20;
            }
        """)

        pagamento_layout.addWidget(self.valor_pagamento)
        pagamento_layout.addWidget(self.descricao_pagamento)
        pagamento_layout.addWidget(self.bt_pagar)

        layout.addLayout(pagamento_layout)

        # ==========================================
        # FECHAR
        # ==========================================
        botoes = QHBoxLayout()

        self.bt_imprimir = QPushButton("🖨️ Imprimir Ficha")
        self.bt_imprimir.setStyleSheet("""
            QPushButton{
                background:#1565C0;
                color:white;
                font-weight:bold;
                padding:6px 16px;
            }
            QPushButton:hover{
                background:#0D47A1;
            }
        """)
        botoes.addWidget(self.bt_imprimir)

        botoes.addStretch()
        self.bt_fechar = QPushButton("Fechar")
        botoes.addWidget(self.bt_fechar)
        layout.addLayout(botoes)

        self.bt_lancar_compra.clicked.connect(self.lancar_compra)
        self.bt_pagar.clicked.connect(self.registrar_pagamento)
        self.bt_imprimir.clicked.connect(self.imprimir_ficha)
        self.bt_fechar.clicked.connect(self.accept)

        self._ficha_atual = None

        self.carregar()

    # ==========================================
    # CARREGAR FICHA
    # ==========================================
    def carregar(self):
        ficha = buscar_ficha(self.cliente["id"])

        if ficha is None:
            QMessageBox.critical(
                self, "Erro", "Não foi possível carregar a ficha do cliente."
            )
            return

        self._ficha_atual = ficha

        saldo = float(ficha["saldo_devedor"])

        self.saldo.setText(f"Saldo devedor: R$ {saldo:.2f}")
        self.saldo.setStyleSheet(
            "font-size:26px; font-weight:bold; color:%s;"
            % ("#C62828" if saldo > 0 else "#2E7D32")
        )

        movimentos = ficha["movimentos"]

        self.tabela.setRowCount(len(movimentos))

        for linha, movimento in enumerate(movimentos):
            data = datetime.fromisoformat(movimento["data"]).strftime(
                "%d/%m/%Y %H:%M"
            )

            tipo = "Compra Fiado" if movimento["tipo"] == "COMPRA" else "Pagamento"

            self.tabela.setItem(linha, 0, QTableWidgetItem(data))
            self.tabela.setItem(linha, 1, QTableWidgetItem(tipo))
            self.tabela.setItem(
                linha, 2, QTableWidgetItem(movimento.get("descricao") or "")
            )
            self.tabela.setItem(
                linha,
                3,
                QTableWidgetItem(f"R$ {float(movimento['valor']):.2f}"),
            )

    # ==========================================
    # LANÇAR COMPRA FIADO
    # ==========================================
    def lancar_compra(self):
        texto = (
            self.valor_compra.text().replace("R$", "").replace(",", ".").strip()
        )

        try:
            valor = float(texto)
            if valor <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(
                self, "Aviso", "Informe um valor de compra válido."
            )
            return

        response = registrar_compra(
            self.cliente["id"],
            valor,
            self.descricao_compra.text() or None,
        )

        if response.status_code == 201:
            QMessageBox.information(
                self, "Sucesso", "Compra fiado lançada com sucesso."
            )
            self.valor_compra.clear()
            self.descricao_compra.clear()
            self.carregar()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", erro)

    # ==========================================
    # IMPRIMIR FICHA
    # ==========================================
    def imprimir_ficha(self):

        if not self._ficha_atual:
            QMessageBox.warning(
                self, "Aviso", "Ficha ainda não carregada."
            )
            return

        impressora_padrao = QPrinterInfo.defaultPrinter()

        if impressora_padrao.isNull():
            QMessageBox.warning(
                self,
                "Impressão",
                "Nenhuma impressora padrão configurada no Windows.",
            )
            return

        config = buscar_configuracoes()
        nome_loja = config.get("nome_loja") or "VERTEX ERP"

        cabecalho_loja = f"<h2 style='text-align:center;'>{nome_loja}</h2>"

        logo_bytes = buscar_logo_bytes()

        if logo_bytes:
            logo_base64 = base64.b64encode(logo_bytes).decode("ascii")
            cabecalho_loja = (
                "<p style='text-align:center;'>"
                f"<img src='data:image/png;base64,{logo_base64}' "
                "height='60'></p>"
            ) + cabecalho_loja

        saldo = float(self._ficha_atual["saldo_devedor"])

        linhas_movimentos = ""

        for movimento in self._ficha_atual["movimentos"]:
            data = datetime.fromisoformat(movimento["data"]).strftime(
                "%d/%m/%Y %H:%M"
            )
            tipo = (
                "Compra Fiado" if movimento["tipo"] == "COMPRA"
                else "Pagamento"
            )

            linhas_movimentos += (
                "<tr>"
                f"<td>{data}</td>"
                f"<td>{tipo}</td>"
                f"<td>{movimento.get('descricao') or ''}</td>"
                f"<td align='right'>R$ {float(movimento['valor']):.2f}</td>"
                "</tr>"
            )

        html = f"""
        {cabecalho_loja}
        <h3 style='text-align:center;'>Ficha do Cliente (Fiado)</h3>
        <p style='text-align:center;'>
            {self.cliente['nome']} — CPF: {self.cliente.get('cpf_cnpj') or '-'}
            — Tel: {self.cliente.get('telefone') or '-'}
        </p>
        <h3 style='text-align:center;'>
            Saldo devedor: R$ {saldo:.2f}
        </h3>
        <table width='100%' cellspacing='0' cellpadding='4'>
            <tr>
                <th align='left'>Data</th>
                <th align='left'>Tipo</th>
                <th align='left'>Descrição</th>
                <th align='right'>Valor</th>
            </tr>
            {linhas_movimentos}
        </table>
        """

        printer = QPrinter(impressora_padrao, QPrinter.HighResolution)

        documento = QTextDocument()
        documento.setHtml(html)
        documento.print_(printer)

    # ==========================================
    # REGISTRAR PAGAMENTO
    # ==========================================
    def registrar_pagamento(self):
        texto = (
            self.valor_pagamento.text().replace("R$", "").replace(",", ".").strip()
        )

        try:
            valor = float(texto)
            if valor <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(
                self, "Aviso", "Informe um valor de pagamento válido."
            )
            return

        response = registrar_pagamento(
            self.cliente["id"],
            valor,
            self.descricao_pagamento.text() or None,
        )

        if response.status_code == 201:
            QMessageBox.information(
                self, "Sucesso", "Pagamento registrado com sucesso."
            )
            self.valor_pagamento.clear()
            self.descricao_pagamento.clear()
            self.carregar()
        else:
            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", erro)
