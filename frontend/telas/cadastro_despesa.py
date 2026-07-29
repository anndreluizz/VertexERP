from datetime import date, datetime

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QDateEdit,
    QComboBox,
    QPushButton,
    QFrame,
    QMessageBox,
)

from services.conta_pagar_service import (
    cadastrar_conta_pagar,
    atualizar_conta_pagar,
)
from services.categoria_despesa_service import listar_categorias_despesa
from telas.gerenciar_categorias_despesa import (
    GerenciarCategoriasDespesaDialog,
)


class CadastroDespesaDialog(QDialog):

    def __init__(self, conta=None, parent=None):

        super().__init__(parent)

        self.conta = conta
        self.conta_salva = None

        editando = conta is not None

        self.setWindowTitle(
            "Editar Despesa" if editando else "+ Nova Despesa"
        )
        self.setFixedSize(420, 540)
        self.setStyleSheet("background:white;")

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QFrame()
        cabecalho.setStyleSheet("background:#202225;")
        cabecalho.setFixedHeight(70)

        cab_layout = QVBoxLayout(cabecalho)
        cab_layout.setContentsMargins(24, 12, 24, 12)
        cab_layout.setSpacing(2)

        titulo = QLabel(
            "EDITAR DESPESA" if editando else "+ NOVA DESPESA"
        )
        titulo.setStyleSheet(
            "background:transparent; color:white; "
            "font-size:16px; font-weight:bold;"
        )

        subtitulo = QLabel("Contas e despesas do estabelecimento")
        subtitulo.setStyleSheet(
            "background:transparent; color:#aaaaaa; font-size:11px;"
        )

        cab_layout.addWidget(titulo)
        cab_layout.addWidget(subtitulo)

        raiz.addWidget(cabecalho)

        # ======================
        # CORPO
        # ======================

        corpo = QVBoxLayout()
        corpo.setContentsMargins(24, 20, 24, 20)
        corpo.setSpacing(14)

        self.descricao = self._campo(
            corpo, "DESCRIÇÃO", "Ex: aluguel, funcionária, luz..."
        )

        cabecalho_categoria = QHBoxLayout()

        lbl_categoria = QLabel("CATEGORIA")
        lbl_categoria.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        bt_gerenciar_categorias = QPushButton("Gerenciar")
        bt_gerenciar_categorias.setAutoDefault(False)
        bt_gerenciar_categorias.setCursor(Qt.PointingHandCursor)
        bt_gerenciar_categorias.setStyleSheet("""
            QPushButton {
                background:transparent;
                border:none;
                color:#1565C0;
                font-size:11px;
                font-weight:bold;
            }
            QPushButton:hover {
                color:#0D47A1;
            }
        """)
        bt_gerenciar_categorias.clicked.connect(
            self.gerenciar_categorias
        )

        cabecalho_categoria.addWidget(lbl_categoria)
        cabecalho_categoria.addStretch()
        cabecalho_categoria.addWidget(bt_gerenciar_categorias)

        self.categoria = QComboBox()
        self.categoria.setMinimumHeight(44)
        self.categoria.setStyleSheet("""
            QComboBox {
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 14px;
                color: #202225;
            }
            QComboBox:focus {
                border: 1px solid #2E7D32;
            }
        """)
        self._carregar_categorias()

        corpo.addLayout(cabecalho_categoria)
        corpo.addWidget(self.categoria)
        self.valor = self._campo(corpo, "VALOR (R$)", "0,00")

        lbl_vencimento = QLabel("VENCIMENTO")
        lbl_vencimento.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        self.vencimento = QDateEdit()
        self.vencimento.setCalendarPopup(True)
        self.vencimento.setDisplayFormat("dd/MM/yyyy")
        self.vencimento.setDate(QDate.currentDate())
        self.vencimento.setMinimumHeight(44)
        self.vencimento.setStyleSheet("""
            QDateEdit {
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 14px;
                color: #202225;
            }
            QDateEdit:focus {
                border: 1px solid #2E7D32;
            }
        """)

        corpo.addWidget(lbl_vencimento)
        corpo.addWidget(self.vencimento)

        self.numero_boleto = self._campo(
            corpo,
            "CÓDIGO DE BARRAS (BOLETO)",
            "Bipe o boleto ou digite a linha digitável",
        )

        corpo.addStretch()

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
        rodape_layout.setSpacing(10)

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

        self.bt_salvar = QPushButton(
            "Salvar Alterações" if editando else "Cadastrar Despesa"
        )
        self.bt_salvar.setMinimumHeight(46)
        self.bt_salvar.setAutoDefault(False)
        self.bt_salvar.setStyleSheet("""
            QPushButton {
                background:#C62828;
                color:white;
                font-weight:bold;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#8E1616;
            }
        """)
        self.bt_salvar.clicked.connect(self.salvar)

        rodape_layout.addWidget(bt_cancelar)
        rodape_layout.addWidget(self.bt_salvar)

        raiz.addWidget(rodape)

        if editando:
            self._preencher(conta)

        self.descricao.setFocus()

    # ======================================

    def _campo(self, layout, rotulo, placeholder):

        lbl = QLabel(rotulo)
        lbl.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        campo = QLineEdit()
        campo.setPlaceholderText(placeholder)
        campo.setMinimumHeight(44)
        campo.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 14px;
                color: #202225;
            }
            QLineEdit:focus {
                border: 1px solid #2E7D32;
            }
        """)

        layout.addWidget(lbl)
        layout.addWidget(campo)

        return campo

    def _carregar_categorias(self):

        selecionada = self.categoria.currentText()

        self.categoria.clear()

        nomes = [
            c["nome"] for c in listar_categorias_despesa()
        ]

        self.categoria.addItems(nomes)

        if selecionada and self.categoria.findText(selecionada) >= 0:
            self.categoria.setCurrentText(selecionada)

    def gerenciar_categorias(self):

        dialogo = GerenciarCategoriasDespesaDialog(parent=self)
        dialogo.exec()

        self._carregar_categorias()

    def _preencher(self, conta):

        self.descricao.setText(conta.get("descricao") or "")
        categoria = conta.get("categoria")
        if categoria and self.categoria.findText(categoria) >= 0:
            self.categoria.setCurrentText(categoria)
        self.numero_boleto.setText(conta.get("numero_boleto") or "")

        valor = conta.get("valor", 0)
        self.valor.setText(
            f"{float(valor):.2f}".replace(".", ",")
        )

        vencimento = conta.get("data_vencimento", "")
        try:
            data = datetime.fromisoformat(vencimento).date()
            self.vencimento.setDate(
                QDate(data.year, data.month, data.day)
            )
        except (ValueError, TypeError):
            pass

    # ======================================

    def salvar(self):

        descricao = self.descricao.text().strip()

        if not descricao:
            QMessageBox.warning(
                self,
                "Atenção",
                "Informe a descrição da despesa.",
            )
            return

        texto_valor = (
            self.valor.text().strip()
            .replace(".", "").replace(",", ".")
        )

        try:
            valor = float(texto_valor)
        except ValueError:
            valor = 0

        if valor <= 0:
            QMessageBox.warning(
                self,
                "Atenção",
                "Informe um valor válido pra despesa.",
            )
            return

        data_qt = self.vencimento.date()
        data_vencimento = date(
            data_qt.year(), data_qt.month(), data_qt.day()
        ).isoformat() + "T00:00:00"

        dados = {
            "descricao": descricao,
            "categoria": self.categoria.currentText(),
            "valor": valor,
            "data_vencimento": data_vencimento,
            "numero_boleto": self.numero_boleto.text().strip() or None,
        }

        if self.conta:
            response = atualizar_conta_pagar(
                self.conta["id"],
                dados,
            )
        else:
            response = cadastrar_conta_pagar(dados)

        if response.status_code in (200, 201):

            self.conta_salva = response.json()

            self.accept()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))
