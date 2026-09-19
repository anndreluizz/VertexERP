from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)
from PySide6.QtCore import QDate

from design import tokens
from design.widgets import BotaoPrimario, BotaoSecundario
from services.fornecedor_service import importar_nfe_preview
from services.compra_service import importar_nfe_confirmar
from services.worker import rodar_em_thread

_FORMAS_PAGAMENTO = ["DINHEIRO", "PIX", "DEBITO", "CREDITO", "BOLETO", "PRAZO"]

# indices das colunas da tabela de revisao
_COL_CODIGO = 0
_COL_DESCRICAO = 1
_COL_STATUS = 2
_COL_QUANTIDADE = 3
_COL_CUSTO = 4
_COL_PRECO_VENDA = 5


class ImportarNFeDialog(QDialog):
    """Sobe um XML de NF-e, mostra o que foi extraido/casado com produtos
    ja cadastrados numa tabela revisavel, e so' grava de verdade
    (fornecedor + produtos + compra + estoque) quando o usuario confirma."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.preview = None
        self.itens_originais = []

        self.setWindowTitle("Importar NF-e")
        self.setMinimumSize(760, 620)
        self.setStyleSheet(f"background:{tokens.FUNDO};")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(24, 20, 24, 20)
        raiz.setSpacing(14)

        titulo = QLabel("Importar NF-e")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        raiz.addWidget(titulo)

        # ---- selecao de arquivo ----

        linha_arquivo = QHBoxLayout()

        self.lbl_arquivo = QLabel("Nenhum arquivo selecionado.")
        self.lbl_arquivo.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_TERCIARIO};"
        )

        self.bt_selecionar = BotaoSecundario("Selecionar XML...")
        self.bt_selecionar.clicked.connect(self.selecionar_arquivo)

        linha_arquivo.addWidget(self.lbl_arquivo, stretch=1)
        linha_arquivo.addWidget(self.bt_selecionar)

        raiz.addLayout(linha_arquivo)

        # ---- fornecedor ----

        self.frame_fornecedor = QFrame()
        self.frame_fornecedor.setStyleSheet(f"""
            background:{tokens.CARD}; border:1px solid {tokens.BORDA};
            border-radius:{tokens.RADIUS_SM}px;
        """)
        fornecedor_layout = QVBoxLayout(self.frame_fornecedor)
        fornecedor_layout.setContentsMargins(14, 12, 14, 12)
        fornecedor_layout.setSpacing(8)

        self.lbl_fornecedor_titulo = QLabel("Fornecedor")
        self.lbl_fornecedor_titulo.setStyleSheet(
            f"background:transparent; font-weight:700; color:{tokens.TEXTO};"
        )

        linha_fornecedor = QHBoxLayout()

        self.fornecedor_razao_social = QLineEdit()
        self.fornecedor_razao_social.setPlaceholderText("Razão social")
        self.fornecedor_razao_social.setMinimumHeight(38)

        self.fornecedor_margem = QDoubleSpinBox()
        self.fornecedor_margem.setRange(0, 999)
        self.fornecedor_margem.setDecimals(2)
        self.fornecedor_margem.setSuffix(" %")
        self.fornecedor_margem.setMinimumHeight(38)
        self.fornecedor_margem.setMinimumWidth(110)
        self.fornecedor_margem.valueChanged.connect(self._recalcular_precos_sugeridos)

        linha_fornecedor.addWidget(self.fornecedor_razao_social, stretch=1)
        linha_fornecedor.addWidget(QLabel("Margem:"))
        linha_fornecedor.addWidget(self.fornecedor_margem)

        self.lbl_fornecedor_cnpj = QLabel("")
        self.lbl_fornecedor_cnpj.setStyleSheet(
            f"background:transparent; color:{tokens.TEXTO_TERCIARIO}; font-size:{tokens.TAMANHO_XS}px;"
        )

        fornecedor_layout.addWidget(self.lbl_fornecedor_titulo)
        fornecedor_layout.addLayout(linha_fornecedor)
        fornecedor_layout.addWidget(self.lbl_fornecedor_cnpj)

        self.frame_fornecedor.setVisible(False)
        raiz.addWidget(self.frame_fornecedor)

        # ---- tabela de itens ----

        self.tabela = QTableWidget()
        self.tabela.setColumnCount(6)
        self.tabela.setHorizontalHeaderLabels(
            ["Código", "Descrição", "Situação", "Quantidade", "Custo", "Preço de Venda"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            _COL_DESCRICAO, QHeaderView.Stretch
        )
        self.tabela.verticalHeader().setDefaultSectionSize(36)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {tokens.BORDA};
                border-radius: {tokens.RADIUS_SM}px;
                color: {tokens.TEXTO};
                background: {tokens.CARD};
                alternate-background-color: {tokens.FUNDO};
            }}
            QHeaderView::section {{
                background: {tokens.FUNDO};
                color: {tokens.TEXTO};
                font-weight: bold;
                padding: 6px;
                border: none;
                border-bottom: 1px solid {tokens.BORDA};
            }}
        """)
        self.tabela.itemChanged.connect(self._ao_editar_item_tabela)

        raiz.addWidget(self.tabela, stretch=1)

        # ---- forma de pagamento ----

        linha_pagamento = QHBoxLayout()

        linha_pagamento.addWidget(QLabel("Forma de pagamento:"))

        self.combo_forma_pagamento = QComboBox()
        self.combo_forma_pagamento.addItems(_FORMAS_PAGAMENTO)
        self.combo_forma_pagamento.currentTextChanged.connect(
            self._ao_mudar_forma_pagamento
        )

        self.data_vencimento = QDateEdit()
        self.data_vencimento.setCalendarPopup(True)
        self.data_vencimento.setDisplayFormat("dd/MM/yyyy")
        self.data_vencimento.setDate(QDate.currentDate())
        self.data_vencimento.setVisible(False)

        linha_pagamento.addWidget(self.combo_forma_pagamento)
        linha_pagamento.addWidget(self.data_vencimento)
        linha_pagamento.addStretch()

        raiz.addLayout(linha_pagamento)

        # ---- rodape ----

        rodape = QHBoxLayout()

        self.bt_cancelar = BotaoSecundario("Cancelar")
        self.bt_cancelar.clicked.connect(self.reject)

        self.bt_confirmar = BotaoPrimario("Confirmar Importação")
        self.bt_confirmar.setEnabled(False)
        self.bt_confirmar.clicked.connect(self.confirmar)

        rodape.addStretch()
        rodape.addWidget(self.bt_cancelar)
        rodape.addWidget(self.bt_confirmar)

        raiz.addLayout(rodape)

    # ======================
    # SELECAO E PREVIEW
    # ======================

    def selecionar_arquivo(self):

        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar NF-e", "", "XML (*.xml)"
        )

        if not caminho:
            return

        try:
            xml_conteudo = Path(caminho).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            xml_conteudo = Path(caminho).read_text(encoding="latin-1")
        except OSError as e:
            QMessageBox.critical(self, "Erro", f"Não foi possível ler o arquivo.\n{e}")
            return

        self.lbl_arquivo.setText(Path(caminho).name)

        self.bt_selecionar.setEnabled(False)
        self.bt_confirmar.setEnabled(False)

        rodar_em_thread(
            self,
            importar_nfe_preview,
            xml_conteudo,
            ao_sucesso=self._ao_preview_sucesso,
            ao_erro=self._ao_preview_erro,
            ao_finalizar=self._ao_preview_finalizado,
        )

    def _ao_preview_sucesso(self, response):

        if response.status_code != 200:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro ao ler NF-e", str(erro))
            return

        self.preview = response.json()
        fornecedor = self.preview["fornecedor"]

        self.frame_fornecedor.setVisible(True)
        self.fornecedor_razao_social.setText(fornecedor.get("razao_social", ""))
        self.fornecedor_margem.setValue(float(fornecedor.get("margem_padrao") or 0))
        self.lbl_fornecedor_cnpj.setText(f"CNPJ: {fornecedor.get('cnpj', '')}")

        if fornecedor.get("encontrado"):
            self.lbl_fornecedor_titulo.setText("Fornecedor (já cadastrado)")
            self.fornecedor_razao_social.setEnabled(False)
        else:
            self.lbl_fornecedor_titulo.setText(
                "Fornecedor novo -- confira/ajuste os dados antes de confirmar"
            )
            self.fornecedor_razao_social.setEnabled(True)

        self._preencher_tabela(self.preview["itens"])
        self.bt_confirmar.setEnabled(True)

    def _ao_preview_erro(self, erro):
        QMessageBox.critical(self, "Erro ao ler NF-e", str(erro))

    def _ao_preview_finalizado(self):
        self.bt_selecionar.setEnabled(True)

    def _preencher_tabela(self, itens):

        self.itens_originais = itens
        self.tabela.blockSignals(True)
        self.tabela.setRowCount(len(itens))

        for linha, item in enumerate(itens):

            novo = item.get("produto_id") is None

            item_codigo = QTableWidgetItem(item["codigo"])
            item_codigo.setFlags(item_codigo.flags() & ~Qt.ItemIsEditable)

            item_descricao = QTableWidgetItem(item["descricao"])
            item_descricao.setFlags(item_descricao.flags() & ~Qt.ItemIsEditable)

            item_status = QTableWidgetItem("Novo" if novo else "Já cadastrado")
            item_status.setFlags(item_status.flags() & ~Qt.ItemIsEditable)
            if novo:
                item_status.setForeground(Qt.darkGreen)
            else:
                item_status.setForeground(Qt.darkBlue)

            item_quantidade = QTableWidgetItem(str(item["quantidade"]))
            item_custo = QTableWidgetItem(f"{float(item['custo']):.2f}")
            item_preco = QTableWidgetItem(f"{float(item['preco_sugerido']):.2f}")

            self.tabela.setItem(linha, _COL_CODIGO, item_codigo)
            self.tabela.setItem(linha, _COL_DESCRICAO, item_descricao)
            self.tabela.setItem(linha, _COL_STATUS, item_status)
            self.tabela.setItem(linha, _COL_QUANTIDADE, item_quantidade)
            self.tabela.setItem(linha, _COL_CUSTO, item_custo)
            self.tabela.setItem(linha, _COL_PRECO_VENDA, item_preco)

        self.tabela.blockSignals(False)

    def _ao_editar_item_tabela(self, item):
        # so' recalcula preco sugerido quando o CUSTO muda -- editar o
        # proprio preco de venda manualmente nao deveria ser sobrescrito
        if item.column() == _COL_CUSTO:
            self._recalcular_preco_linha(item.row())

    def _recalcular_preco_linha(self, linha):

        try:
            custo = float(self.tabela.item(linha, _COL_CUSTO).text().replace(",", "."))
        except (ValueError, AttributeError):
            return

        margem = self.fornecedor_margem.value()
        sugerido = custo * (1 + margem / 100)

        self.tabela.blockSignals(True)
        self.tabela.setItem(
            linha, _COL_PRECO_VENDA, QTableWidgetItem(f"{sugerido:.2f}")
        )
        self.tabela.blockSignals(False)

    def _recalcular_precos_sugeridos(self):
        for linha in range(self.tabela.rowCount()):
            self._recalcular_preco_linha(linha)

    def _ao_mudar_forma_pagamento(self, forma):
        self.data_vencimento.setVisible(forma == "PRAZO")

    # ======================
    # CONFIRMACAO
    # ======================

    def confirmar(self):

        if not self.itens_originais:
            return

        razao_social = self.fornecedor_razao_social.text().strip()

        if not razao_social:
            QMessageBox.warning(self, "Atenção", "Informe a razão social do fornecedor.")
            return

        try:
            itens_payload = []
            for linha, original in enumerate(self.itens_originais):
                itens_payload.append({
                    "produto_id": original.get("produto_id"),
                    "codigo": original["codigo"],
                    "descricao": original["descricao"],
                    "codigo_barras": original.get("codigo_barras"),
                    "quantidade": int(self.tabela.item(linha, _COL_QUANTIDADE).text()),
                    "custo": self.tabela.item(linha, _COL_CUSTO).text().replace(",", "."),
                    "preco_venda": self.tabela.item(linha, _COL_PRECO_VENDA).text().replace(",", "."),
                })
        except (ValueError, AttributeError):
            QMessageBox.warning(
                self, "Atenção",
                "Confira quantidade/custo/preço -- algum valor não é um número válido."
            )
            return

        fornecedor = self.preview["fornecedor"]

        payload = {
            "forma_pagamento": self.combo_forma_pagamento.currentText(),
            "itens": itens_payload,
        }

        if self.combo_forma_pagamento.currentText() == "PRAZO":
            payload["data_vencimento"] = self.data_vencimento.date().toString(
                "yyyy-MM-dd"
            )

        if fornecedor.get("encontrado"):
            payload["fornecedor_id"] = fornecedor["id"]
        else:
            payload["fornecedor_novo"] = {
                "razao_social": razao_social,
                "nome_fantasia": fornecedor.get("nome_fantasia"),
                "cnpj": fornecedor["cnpj"],
                "margem_padrao": self.fornecedor_margem.value(),
            }

        self.bt_confirmar.setEnabled(False)
        self.bt_cancelar.setEnabled(False)

        rodar_em_thread(
            self,
            importar_nfe_confirmar,
            payload,
            ao_sucesso=self._ao_confirmar_sucesso,
            ao_erro=self._ao_confirmar_erro,
            ao_finalizar=self._ao_confirmar_finalizado,
        )

    def _ao_confirmar_sucesso(self, response):

        if response.status_code == 200:
            compra = response.json()
            QMessageBox.information(
                self, "Importação concluída",
                f"Compra #{compra['id']} registrada com sucesso -- "
                f"produtos e estoque atualizados."
            )
            self.accept()
        else:
            try:
                erro = response.json().get("detail") or str(response.json())
            except Exception:
                erro = response.text
            QMessageBox.critical(self, "Erro ao confirmar", str(erro))

    def _ao_confirmar_erro(self, erro):
        QMessageBox.critical(self, "Erro ao confirmar", str(erro))

    def _ao_confirmar_finalizado(self):
        self.bt_confirmar.setEnabled(True)
        self.bt_cancelar.setEnabled(True)
