from PySide6.QtCore import Qt, QTimer, Signal, QEvent
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QWidget,
)

from services.pdv_service import pesquisar_produtos
from services.produto_service import obter_foto_produto


class ItemResultado(QWidget):

    def __init__(self, produto):

        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(12)

        icone = QLabel()
        icone.setFixedSize(38, 38)
        icone.setAlignment(Qt.AlignCenter)
        icone.setStyleSheet("""
            background:#eef0f3;
            border-radius:8px;
            font-size:18px;
        """)

        pixmap_foto = self._carregar_foto(produto) if produto.get("tem_foto") else None

        if pixmap_foto:
            icone.setPixmap(pixmap_foto)
        else:
            icone.setText("📦")

        col_texto = QVBoxLayout()
        col_texto.setSpacing(0)

        nome_texto = produto["nome"].upper()
        if produto.get("favorito"):
            nome_texto = f"★ {nome_texto}"

        nome = QLabel(nome_texto)
        nome.setStyleSheet(
            "font-weight:bold; font-size:13px; background:transparent;"
        )

        codigo_ref = produto.get("codigo_barras") or produto["codigo"]

        subtitulo = QLabel(
            f"UN · Estoque: {produto['estoque']} · Cód: {codigo_ref}"
        )
        subtitulo.setStyleSheet(
            "font-size:11px; color:gray; background:transparent;"
        )

        col_texto.addWidget(nome)
        col_texto.addWidget(subtitulo)

        preco = QLabel(f"R$ {float(produto['preco']):.2f}")
        preco.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        preco.setStyleSheet(
            "font-size:14px; font-weight:bold; background:transparent;"
        )

        layout.addWidget(icone)
        layout.addLayout(col_texto)
        layout.addStretch()
        layout.addWidget(preco)

    def _carregar_foto(self, produto):

        bruto = obter_foto_produto(produto["id"])

        if not bruto:
            return None

        pixmap = QPixmap()

        if not pixmap.loadFromData(bruto):
            return None

        return pixmap.scaled(
            38, 38, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        )


class BuscarProdutoDialog(QDialog):

    produto_selecionado = Signal(dict, int)

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setWindowTitle("Pesquisar Produto (F1)")
        self.resize(680, 520)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        titulo = QLabel("Pesquisar Produto (F1)")
        titulo.setStyleSheet(
            "background:transparent; font-size:16px; "
            "font-weight:bold; color:#202225;"
        )

        layout.addWidget(titulo)

        self.busca = QLineEdit()
        self.busca.setPlaceholderText(
            "Digite o nome ou código de barras... "
            "(ex.: 2*7891000100103)"
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

        linha_busca = QHBoxLayout()
        linha_busca.setSpacing(8)
        linha_busca.addWidget(self.busca, stretch=1)

        self.bt_favoritos = QPushButton("★ Favoritos")
        self.bt_favoritos.setCheckable(True)
        self.bt_favoritos.setMinimumHeight(40)
        self.bt_favoritos.setCursor(Qt.PointingHandCursor)
        self.bt_favoritos.setStyleSheet("""
            QPushButton {
                background:white; color:#B45309;
                border:1px solid #cccccc; border-radius:8px;
                padding:0 14px; font-size:13px; font-weight:bold;
            }
            QPushButton:checked {
                background:#FFFBEB; border:1px solid #B45309;
            }
        """)
        self.bt_favoritos.toggled.connect(lambda _checked: self.executar_busca())
        linha_busca.addWidget(self.bt_favoritos)

        layout.addLayout(linha_busca)

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
            "Nenhum produto encontrado.\n"
            "Bipe ou digite o código de barras, ou o nome do produto."
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

        self.busca.setFocus()

        self.executar_busca()

    # ==================================================

    def parse_quantidade_termo(self, texto):

        if "*" in texto:

            qtd_str, _, termo = texto.partition("*")

            try:
                qtd = int(qtd_str.strip())
                if qtd < 1:
                    qtd = 1
            except ValueError:
                qtd = 1

            return qtd, termo.strip()

        return 1, texto.strip()

    def agendar_busca(self):
        self.timer_busca.start(250)

    def executar_busca(self):

        _, termo = self.parse_quantidade_termo(self.busca.text())

        self.lista.clear()

        # termo vazio = lista os produtos cadastrados (navegavel),
        # sem precisar digitar nada pra ver algo na tela
        produtos = pesquisar_produtos(termo)

        if self.bt_favoritos.isChecked():
            produtos = [p for p in produtos if p.get("favorito")]

        for produto in produtos:

            item = QListWidgetItem()
            item.setSizeHint(ItemResultado(produto).sizeHint())
            item.setData(Qt.UserRole, produto)

            self.lista.addItem(item)
            self.lista.setItemWidget(item, ItemResultado(produto))

        if self.lista.count() > 0:
            self.lista.setCurrentRow(0)

        self.lista.setVisible(self.lista.count() > 0)
        self.lbl_vazio.setVisible(self.lista.count() == 0)

        if self.lista.count() == 0:
            if self.bt_favoritos.isChecked():
                self.lbl_vazio.setText(
                    "Nenhum produto favorito encontrado.\n"
                    "Marque produtos como favoritos na tela de Estoque."
                )
            elif termo:
                self.lbl_vazio.setText(
                    f"Nenhum produto encontrado para \"{termo}\"."
                )
            else:
                self.lbl_vazio.setText(
                    "Nenhum produto cadastrado ainda.\n"
                    "Cadastre produtos na tela de Estoque."
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
                self.close()
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

        produto = item.data(Qt.UserRole)
        quantidade, _ = self.parse_quantidade_termo(self.busca.text())

        self.produto_selecionado.emit(produto, quantidade)

        self.busca.clear()
        self.executar_busca()
        self.busca.setFocus()
