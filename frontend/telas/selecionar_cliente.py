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
from services.worker import rodar_em_thread
from telas.cadastro_cliente import CadastroClienteDialog
from design import tokens


def _pesquisar_clientes(sequencia, termo):
    """Roda na worker thread -- a sequencia viaja junto com o
    resultado (mesmo padrao de telas/buscar_produto.py) pra quem
    recebe saber se ainda e' a busca mais recente."""

    ativos = [c for c in listar_clientes() if c.get("ativo", True)]

    if termo:
        clientes = [
            c
            for c in ativos
            if termo in (c.get("nome") or "").lower()
            or termo in (c.get("telefone") or "").lower()
            or termo in (c.get("cpf_cnpj") or "").lower()
        ]
    else:
        clientes = ativos

    return sequencia, termo, ativos, clientes


class ItemResultadoCliente(QWidget):

    def __init__(self, cliente):

        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(12)

        icone = QLabel("👤")
        icone.setFixedSize(38, 38)
        icone.setAlignment(Qt.AlignCenter)
        icone.setStyleSheet(f"""
            background:{tokens.FUNDO};
            border-radius:19px;
            font-size:16px;
        """)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(0)

        nome = QLabel(cliente["nome"])
        nome.setStyleSheet(
            "font-weight:bold; font-size:13px; "
            f"color:{tokens.TEXTO}; background:transparent;"
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
            f"font-size:11px; color:{tokens.TEXTO_SECUNDARIO}; background:transparent;"
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
        self.setStyleSheet(f"background:{tokens.CARD};")

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        titulo = QLabel("Selecionar Cliente")
        titulo.setStyleSheet(
            "background:transparent; font-size:16px; "
            f"font-weight:bold; color:{tokens.TEXTO};"
        )

        layout.addWidget(titulo)

        self.busca = QLineEdit()
        self.busca.setPlaceholderText(
            "Digite o nome, whatsapp ou CPF do cliente..."
        )
        self.busca.setMinimumHeight(40)
        self.busca.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {tokens.BORDA};
                border-radius: 8px;
                padding: 0 12px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 1px solid {tokens.SECUNDARIA};
            }}
        """)
        self.busca.installEventFilter(self)
        self.busca.textChanged.connect(self.agendar_busca)

        layout.addWidget(self.busca)

        bt_novo = QPushButton("+ Novo Cliente")
        bt_novo.setMinimumHeight(40)
        bt_novo.setAutoDefault(False)
        bt_novo.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.SECUNDARIA};
                color:{tokens.TEXTO_CLARO};
                font-weight:bold;
                border-radius:8px;
            }}
            QPushButton:hover {{
                background:{tokens.SECUNDARIA_HOVER};
            }}
        """)
        bt_novo.clicked.connect(self.novo_cliente)

        layout.addWidget(bt_novo)

        self.lista = QListWidget()
        self.lista.setStyleSheet(f"""
            QListWidget {{
                border: 1px solid {tokens.BORDA};
                border-radius: 8px;
            }}
            QListWidget::item:selected {{
                background: {tokens.PRIMARIA};
            }}
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
            f"background:transparent; color:{tokens.TEXTO_SECUNDARIO}; font-size:13px;"
        )
        self.lbl_vazio.setVisible(False)

        layout.addWidget(self.lbl_vazio, stretch=1)

        rodape = QHBoxLayout()

        dica_esquerda = QLabel("↑↓ Navegar    Enter Selecionar")
        dica_esquerda.setStyleSheet(f"font-size:11px; color:{tokens.TEXTO_SECUNDARIO};")

        dica_direita = QLabel("Esc Fechar")
        dica_direita.setStyleSheet(f"font-size:11px; color:{tokens.TEXTO_SECUNDARIO};")

        rodape.addWidget(dica_esquerda)
        rodape.addStretch()
        rodape.addWidget(dica_direita)

        layout.addLayout(rodape)

        self.timer_busca = QTimer(self)
        self.timer_busca.setSingleShot(True)
        self.timer_busca.timeout.connect(self.executar_busca)

        self._clientes_ativos = []
        self._busca_sequencia = 0

        self.busca.setFocus()

        self.executar_busca()

    # ==================================================

    def agendar_busca(self):
        self.timer_busca.start(250)

    def executar_busca(self):

        termo = self.busca.text().strip().lower()

        self._busca_sequencia += 1

        rodar_em_thread(
            self,
            _pesquisar_clientes,
            self._busca_sequencia,
            termo,
            ao_sucesso=self._ao_busca_sucesso,
            ao_erro=self._ao_busca_erro,
        )

    def _ao_busca_erro(self, erro):
        self.lista.clear()
        self.lista.setVisible(False)
        self.lbl_vazio.setText(f"Não foi possível buscar clientes.\n{erro}")
        self.lbl_vazio.setVisible(True)

    def _ao_busca_sucesso(self, resultado):

        sequencia, termo, ativos, clientes = resultado

        if sequencia != self._busca_sequencia:
            return  # resposta de uma busca ja' superada, ignora

        self._clientes_ativos = ativos

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
