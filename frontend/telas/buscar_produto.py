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
from utils.formatacao import formatar_moeda
from design import tokens


class ItemResultado(QWidget):

    def __init__(self, produto):

        super().__init__()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(12)

        icone = QLabel()
        icone.setFixedSize(38, 38)
        icone.setAlignment(Qt.AlignCenter)
        icone.setStyleSheet(f"""
            background:{tokens.FUNDO};
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

        sem_estoque = produto["estoque"] <= 0
        texto_estoque = (
            "SEM ESTOQUE" if sem_estoque else f"Estoque: {produto['estoque']}"
        )

        subtitulo = QLabel(
            f"UN · {texto_estoque} · Cód: {codigo_ref}"
        )
        subtitulo.setStyleSheet(
            f"font-size:11px; background:transparent; "
            f"color:{tokens.ERRO if sem_estoque else tokens.TEXTO_SECUNDARIO}; "
            f"font-weight:{'bold' if sem_estoque else 'normal'};"
        )

        if sem_estoque:
            nome.setStyleSheet(
                "font-weight:bold; font-size:13px; background:transparent; "
                f"color:{tokens.TEXTO_TERCIARIO};"
            )

        col_texto.addWidget(nome)
        col_texto.addWidget(subtitulo)

        preco = QLabel(formatar_moeda(produto["preco"]))
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
            f"font-weight:bold; color:{tokens.TEXTO};"
        )

        layout.addWidget(titulo)

        self.busca = QLineEdit()
        self.busca.setPlaceholderText(
            "Digite o nome ou código de barras... "
            "(ex.: 2*7891000100103)"
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

        linha_busca = QHBoxLayout()
        linha_busca.setSpacing(8)
        linha_busca.addWidget(self.busca, stretch=1)

        self.bt_favoritos = QPushButton("★ Favoritos")
        self.bt_favoritos.setCheckable(True)
        self.bt_favoritos.setMinimumHeight(40)
        self.bt_favoritos.setCursor(Qt.PointingHandCursor)
        self.bt_favoritos.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; color:{tokens.ALERTA_TEXTO};
                border:1px solid {tokens.BORDA}; border-radius:8px;
                padding:0 14px; font-size:13px; font-weight:bold;
            }}
            QPushButton:checked {{
                background:{tokens.ALERTA_CLARO}; border:1px solid {tokens.ALERTA_TEXTO};
            }}
        """)
        self.bt_favoritos.toggled.connect(lambda _checked: self.executar_busca())
        linha_busca.addWidget(self.bt_favoritos)

        layout.addLayout(linha_busca)

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
            "Nenhum produto encontrado.\n"
            "Bipe ou digite o código de barras, ou o nome do produto."
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
