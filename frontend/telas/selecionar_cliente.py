from PySide6.QtCore import Qt, QTimer, Signal, QEvent
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QWidget,
)

from services.cliente_service import listar_clientes
from telas.cadastro_cliente import CadastroClienteDialog


class ItemResultadoCliente(QWidget):

    def __init__(self, cliente):

        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(12)

        icone = QLabel("👤")
        icone.setFixedSize(38, 38)
        icone.setAlignment(Qt.AlignCenter)
        icone.setStyleSheet("""
            background:#eef0f3;
            border-radius:19px;
            font-size:16px;
        """)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(0)

        nome = QLabel(cliente["nome"])
        nome.setStyleSheet(
            "font-weight:bold; font-size:13px; "
            "color:#202225; background:transparent;"
        )

        detalhes = " · ".join(
            filter(
                None,
                [
                    cliente.get("telefone"),
                    cliente.get("cpf_cnpj"),
                ],
            )
        ) or "Sem contato cadastrado"

        subtitulo = QLabel(detalhes)
        subtitulo.setStyleSheet(
            "font-size:11px; color:gray; background:transparent;"
        )

        col_texto.addWidget(nome)
        col_texto.addWidget(subtitulo)

        layout.addWidget(icone)
        layout.addLayout(col_texto)
        layout.addStretch()


class SelecionarClienteDialog(QDialog):

    cliente_selecionado = Signal(dict)

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setWindowTitle("Selecionar Cliente")
        self.resize(560, 520)
        self.setStyleSheet("background:white;")

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        titulo = QLabel("Selecionar Cliente")
        titulo.setStyleSheet(
            "background:transparent; font-size:16px; "
            "font-weight:bold; color:#202225;"
        )

        layout.addWidget(titulo)

        self.busca = QLineEdit()
        self.busca.setPlaceholderText(
            "Digite o nome, whatsapp ou CPF do cliente..."
        )
        self.busca.setMinimumHeight(40)
        self.busca.setStyleSheet("""
            QLineEdit {
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #2E7D32;
            }
        """)
        self.busca.installEventFilter(self)
        self.busca.textChanged.connect(self.agendar_busca)

        layout.addWidget(self.busca)

        bt_novo = QPushButton("+ Novo Cliente")
        bt_novo.setMinimumHeight(40)
        bt_novo.setAutoDefault(False)
        bt_novo.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                color:white;
                font-weight:bold;
                border-radius:8px;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
        """)
        bt_novo.clicked.connect(self.novo_cliente)

        layout.addWidget(bt_novo)

        self.lista = QListWidget()
        self.lista.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            QListWidget::item:selected {
                background: #1565C0;
            }
        """)
        self.lista.itemClicked.connect(self.selecionar_atual)

        layout.addWidget(self.lista, stretch=1)

        self.lbl_vazio = QLabel(
            "Nenhum cliente encontrado.\n"
            "Cadastre um novo cliente pra começar o fiado dele."
        )
        self.lbl_vazio.setAlignment(Qt.AlignCenter)
        self.lbl_vazio.setWordWrap(True)
        self.lbl_vazio.setStyleSheet(
            "background:transparent; color:gray; font-size:13px;"
        )
        self.lbl_vazio.setVisible(False)

        layout.addWidget(self.lbl_vazio, stretch=1)

        rodape = QHBoxLayout()

        dica_esquerda = QLabel("↑↓ Navegar    Enter Selecionar")
        dica_esquerda.setStyleSheet("font-size:11px; color:gray;")

        dica_direita = QLabel("Esc Fechar")
        dica_direita.setStyleSheet("font-size:11px; color:gray;")

        rodape.addWidget(dica_esquerda)
        rodape.addStretch()
        rodape.addWidget(dica_direita)

        layout.addLayout(rodape)

        self.timer_busca = QTimer(self)
        self.timer_busca.setSingleShot(True)
        self.timer_busca.timeout.connect(self.executar_busca)

        self._clientes_ativos = []

        self.busca.setFocus()

        self.executar_busca()

    # ==================================================

    def agendar_busca(self):
        self.timer_busca.start(250)

    def executar_busca(self):

        termo = self.busca.text().strip().lower()

        self._clientes_ativos = [
            c for c in listar_clientes() if c.get("ativo", True)
        ]

        if termo:
            clientes = [
                c
                for c in self._clientes_ativos
                if termo in (c.get("nome") or "").lower()
                or termo in (c.get("telefone") or "").lower()
                or termo in (c.get("cpf_cnpj") or "").lower()
            ]
        else:
            clientes = self._clientes_ativos

        self.lista.clear()

        for cliente in clientes:

            item = QListWidgetItem()
            item.setSizeHint(ItemResultadoCliente(cliente).sizeHint())
            item.setData(Qt.UserRole, cliente)

            self.lista.addItem(item)
            self.lista.setItemWidget(
                item, ItemResultadoCliente(cliente)
            )

        if self.lista.count() > 0:
            self.lista.setCurrentRow(0)

        self.lista.setVisible(self.lista.count() > 0)
        self.lbl_vazio.setVisible(self.lista.count() == 0)

        if self.lista.count() == 0:
            if termo:
                self.lbl_vazio.setText(
                    f'Nenhum cliente encontrado para "{termo}".'
                )
            else:
                self.lbl_vazio.setText(
                    "Nenhum cliente cadastrado ainda.\n"
                    "Cadastre um novo cliente pra começar o fiado dele."
                )

    # ==================================================

    def eventFilter(self, obj, event):

        if obj is self.busca and event.type() == QEvent.KeyPress:

            if event.key() == Qt.Key_Down:
                self._mover_selecao(1)
                return True

            if event.key() == Qt.Key_Up:
                self._mover_selecao(-1)
                return True

            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.selecionar_atual()
                return True

            if event.key() == Qt.Key_Escape:
                self.reject()
                return True

        return super().eventFilter(obj, event)

    def _mover_selecao(self, delta):

        if self.lista.count() == 0:
            return

        linha = self.lista.currentRow()
        nova = max(0, min(self.lista.count() - 1, linha + delta))

        self.lista.setCurrentRow(nova)

    def selecionar_atual(self, *_args):

        item = self.lista.currentItem()

        if item is None:
            return

        cliente = item.data(Qt.UserRole)

        self.cliente_selecionado.emit(cliente)

        self.accept()

    # ==================================================

    def novo_cliente(self):

        dialogo = CadastroClienteDialog(parent=self)

        if dialogo.exec() != QDialog.Accepted:
            return

        if not dialogo.cliente_salvo:
            return

        self.cliente_selecionado.emit(dialogo.cliente_salvo)

        self.accept()
