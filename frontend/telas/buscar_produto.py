from PySide6.QtCore import Qt, QTimer, Signal, QEvent
from PySide6.QtGui import QPixmap, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QWidget,
)

from services.pdv_service import pesquisar_produtos
from services.produto_service import obter_foto_produto, alternar_favorito_produto
from services.worker import rodar_em_thread
from utils.formatacao import formatar_moeda
from design import tokens
from design.icons import icone, icone_pixmap
from design.widgets import Badge

_TAMANHO_FOTO = 64


def _executar_pesquisa(sequencia, termo, so_favoritos):
    """Roda na worker thread -- a sequencia so' viaja de ida e volta
    junto com o resultado (ver BuscarProdutoDialog._ao_busca_sucesso)
    pra quem recebe saber se essa resposta ainda e' da busca mais
    recente ou se o usuario ja digitou de novo enquanto ela voltava."""
    produtos = pesquisar_produtos(termo)
    if so_favoritos:
        produtos = [p for p in produtos if p.get("favorito")]
    return sequencia, termo, produtos


def _pixmap_arredondado(pixmap, tamanho, raio=10):

    origem = pixmap.scaled(
        tamanho, tamanho, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation,
    )

    if origem.width() != tamanho or origem.height() != tamanho:
        x = (origem.width() - tamanho) // 2
        y = (origem.height() - tamanho) // 2
        origem = origem.copy(x, y, tamanho, tamanho)

    arredondado = QPixmap(tamanho, tamanho)
    arredondado.fill(Qt.transparent)

    painter = QPainter(arredondado)
    painter.setRenderHint(QPainter.Antialiasing)

    caminho = QPainterPath()
    caminho.addRoundedRect(0, 0, tamanho, tamanho, raio, raio)
    painter.setClipPath(caminho)

    painter.drawPixmap(0, 0, origem)
    painter.end()

    return arredondado


class ItemResultado(QWidget):
    """Card de um resultado da pesquisa -- pinta a si mesmo diferente
    quando é a linha atual (`destacar`), porque o widget customizado
    fica por cima do próprio destaque nativo do QListWidget (por isso
    a lista usa QListWidget::item:selected transparente, ver
    BuscarProdutoDialog)."""

    favorito_alterado = Signal()

    def __init__(self, produto):

        super().__init__()

        # QWidget puro ignora background/border do stylesheet por
        # padrao (soh QFrame e alguns outros pintam isso sozinhos) --
        # sem isso, destacar() nao tinha efeito visual nenhum: nem o
        # card branco com borda das linhas normais, nem o azul da
        # linha selecionada apareciam.
        self.setAttribute(Qt.WA_StyledBackground, True)

        self.produto = produto

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(14)

        self.lbl_foto = QLabel()
        self.lbl_foto.setFixedSize(_TAMANHO_FOTO, _TAMANHO_FOTO)
        self.lbl_foto.setAlignment(Qt.AlignCenter)
        self.lbl_foto.setStyleSheet(f"""
            background:{tokens.FUNDO}; border-radius:{tokens.RADIUS_SM}px; border:none;
        """)

        pixmap_foto = self._carregar_foto() if produto.get("tem_foto") else None

        if pixmap_foto:
            self.lbl_foto.setPixmap(
                _pixmap_arredondado(pixmap_foto, _TAMANHO_FOTO - 4, raio=8)
            )
        else:
            self.lbl_foto.setPixmap(
                icone_pixmap("package", cor=tokens.TEXTO_TERCIARIO, tamanho=22)
            )

        layout.addWidget(self.lbl_foto)

        col_texto = QVBoxLayout()
        col_texto.setSpacing(4)

        linha_nome = QHBoxLayout()
        linha_nome.setSpacing(8)

        nome = QLabel(produto["nome"].upper())
        nome.setWordWrap(True)
        nome.setStyleSheet(f"""
            background:transparent; border:none; font-weight:800;
            font-size:{tokens.TAMANHO_MD}px; color:{tokens.TEXTO};
        """)
        linha_nome.addWidget(nome, 1)

        if produto.get("favorito"):
            linha_nome.addWidget(Badge("favorito", "info"))

        col_texto.addLayout(linha_nome)

        linha_sub = QHBoxLayout()
        linha_sub.setSpacing(6)

        unidade = produto.get("unidade") or "UN"
        lbl_unidade = QLabel(f"{unidade} ·")
        lbl_unidade.setStyleSheet(self._estilo_texto_secundario())
        linha_sub.addWidget(lbl_unidade)

        sem_estoque = produto["estoque"] <= 0

        if sem_estoque:
            linha_sub.addWidget(Badge("SEM ESTOQUE", "erro"))
        else:
            lbl_estoque = QLabel(f"Estoque: {produto['estoque']}")
            lbl_estoque.setStyleSheet(self._estilo_texto_secundario())
            linha_sub.addWidget(lbl_estoque)

        codigo_ref = produto.get("codigo_barras") or produto["codigo"]
        lbl_codigo = QLabel(f"· Cód: {codigo_ref}")
        lbl_codigo.setStyleSheet(self._estilo_texto_secundario())
        linha_sub.addWidget(lbl_codigo)
        linha_sub.addStretch()

        col_texto.addLayout(linha_sub)

        layout.addLayout(col_texto, 1)

        col_direita = QVBoxLayout()
        col_direita.setSpacing(4)
        col_direita.setAlignment(Qt.AlignCenter)

        preco = QLabel(formatar_moeda(produto["preco"]))
        preco.setAlignment(Qt.AlignRight)
        preco.setStyleSheet(f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_LG}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        col_direita.addWidget(preco)

        self.bt_favorito = QPushButton()
        self.bt_favorito.setFixedSize(30, 30)
        self.bt_favorito.setCursor(Qt.PointingHandCursor)
        self.bt_favorito.setToolTip("Marcar/desmarcar como favorito")
        self.bt_favorito.setAccessibleName("Marcar ou desmarcar como favorito")
        self.bt_favorito.setStyleSheet(f"""
            QPushButton {{ background:transparent; border:none; border-radius:15px; }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        self.bt_favorito.clicked.connect(self._alternar_favorito)
        self._atualizar_icone_favorito()
        col_direita.addWidget(self.bt_favorito, 0, Qt.AlignRight)

        layout.addLayout(col_direita)

        self.destacar(False)

    def _estilo_texto_secundario(self):
        return f"""
            background:transparent; border:none; font-size:{tokens.TAMANHO_SM}px;
            color:{tokens.TEXTO_SECUNDARIO};
        """

    def destacar(self, ativo):

        self.setStyleSheet(f"""
            ItemResultado {{
                background:{tokens.PRIMARIA_CLARA if ativo else tokens.CARD};
                border:1.5px solid {tokens.PRIMARIA if ativo else tokens.BORDA};
                border-radius:{tokens.RADIUS_MD}px;
            }}
        """)

    def _carregar_foto(self):

        bruto = obter_foto_produto(self.produto["id"])

        if not bruto:
            return None

        pixmap = QPixmap()

        if not pixmap.loadFromData(bruto):
            return None

        return pixmap

    def _atualizar_icone_favorito(self):

        if self.produto.get("favorito"):
            self.bt_favorito.setIcon(icone("star-filled", cor=tokens.PRIMARIA, tamanho=18))
        else:
            self.bt_favorito.setIcon(icone("star", cor=tokens.TEXTO_TERCIARIO, tamanho=18))

    def _alternar_favorito(self):

        novo_valor = not self.produto.get("favorito", False)

        response = alternar_favorito_produto(
            self.produto["id"], self.produto["codigo"], self.produto["nome"], novo_valor,
        )

        if response.status_code != 200:
            QMessageBox.warning(
                self, "Aviso", "Não foi possível atualizar o favorito agora."
            )
            return

        self.produto["favorito"] = novo_valor
        self._atualizar_icone_favorito()

        # a lista pode estar filtrada por "Favoritos" -- precisa
        # reconstruir pra esse item sumir/aparecer certo. Adiada pro
        # próximo giro do loop de eventos porque disparar isso direto
        # aqui destruiria este próprio widget no meio do seu clique.
        QTimer.singleShot(0, self.favorito_alterado.emit)


class BuscarProdutoDialog(QDialog):

    produto_selecionado = Signal(dict, int)

    def __init__(self, parent=None):

        super().__init__(parent)

        self.setWindowTitle("Pesquisar Produto (F1)")
        self.resize(820, 640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # ---- cabeçalho ----

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(12)

        icone_titulo = QLabel()
        icone_titulo.setFixedSize(44, 44)
        icone_titulo.setAlignment(Qt.AlignCenter)
        icone_titulo.setStyleSheet(f"""
            background:{tokens.PRIMARIA_CLARA}; border-radius:{tokens.RADIUS_MD}px;
        """)
        icone_titulo.setPixmap(icone_pixmap("search", cor=tokens.PRIMARIA, tamanho=20))
        cabecalho.addWidget(icone_titulo)

        titulo = QLabel("Pesquisar Produto (F1)")
        titulo.setStyleSheet(f"""
            background:transparent; font-size:{tokens.TAMANHO_XL}px;
            font-weight:800; color:{tokens.TEXTO};
        """)
        cabecalho.addWidget(titulo)
        cabecalho.addStretch()

        bt_fechar = QPushButton()
        bt_fechar.setFixedSize(34, 34)
        bt_fechar.setCursor(Qt.PointingHandCursor)
        bt_fechar.setIcon(icone("x", cor=tokens.TEXTO_TERCIARIO, tamanho=16))
        bt_fechar.setToolTip("Fechar")
        bt_fechar.setAccessibleName("Fechar")
        bt_fechar.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.CARD}; border:1px solid {tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
            }}
            QPushButton:hover {{ background:{tokens.FUNDO}; }}
        """)
        bt_fechar.clicked.connect(self.close)
        cabecalho.addWidget(bt_fechar)

        layout.addLayout(cabecalho)

        # ---- busca ----

        self.busca = QLineEdit()
        self.busca.setPlaceholderText(
            "Digite o nome ou código de barras... "
            "(ex.: 2*7891000100103)"
        )
        self.busca.setMinimumHeight(44)
        self.busca.addAction(
            icone("search", cor=tokens.TEXTO_TERCIARIO, tamanho=16),
            QLineEdit.LeadingPosition,
        )
        self.busca.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid {tokens.BORDA}; border-radius: {tokens.RADIUS_SM}px;
                padding: 0 12px; font-size: {tokens.TAMANHO_MD}px; color: {tokens.TEXTO};
                background: {tokens.CARD};
            }}
            QLineEdit:focus {{ border: 1.5px solid {tokens.PRIMARIA}; }}
        """)
        self.busca.installEventFilter(self)
        self.busca.textChanged.connect(self.agendar_busca)

        linha_busca = QHBoxLayout()
        linha_busca.setSpacing(8)
        linha_busca.addWidget(self.busca, stretch=1)

        self.bt_favoritos = QPushButton("Favoritos")
        self.bt_favoritos.setCheckable(True)
        self.bt_favoritos.setCursor(Qt.PointingHandCursor)
        self.bt_favoritos.setMinimumHeight(44)
        self.bt_favoritos.toggled.connect(self._atualizar_estilo_favoritos)
        self._atualizar_estilo_favoritos(False)
        self.bt_favoritos.toggled.connect(lambda _checked: self.executar_busca())
        linha_busca.addWidget(self.bt_favoritos)

        layout.addLayout(linha_busca)

        self.lista = QListWidget()
        self.lista.setSpacing(6)
        self.lista.setStyleSheet(f"""
            QListWidget {{
                border: none; background: transparent;
            }}
            QListWidget::item {{
                border: none;
            }}
            QListWidget::item:selected {{
                background: transparent;
            }}
        """)
        self.lista.itemClicked.connect(self.selecionar_atual)
        self.lista.currentRowChanged.connect(self._destacar_linha_atual)

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

        dica_esquerda = QLabel("↑↓ Navegar    |    Enter Selecionar")
        dica_esquerda.setStyleSheet(f"font-size:11px; color:{tokens.TEXTO_SECUNDARIO};")

        dica_direita = QLabel("Esc Fechar")
        dica_direita.setStyleSheet(f"font-size:11px; color:{tokens.TEXTO_SECUNDARIO};")

        rodape.addWidget(dica_esquerda)
        rodape.addStretch()
        rodape.addWidget(dica_direita)

        layout.addLayout(rodape)

        self._busca_sequencia = 0

        self.timer_busca = QTimer(self)
        self.timer_busca.setSingleShot(True)
        self.timer_busca.timeout.connect(self.executar_busca)

        self.busca.setFocus()

        self.executar_busca()

    # ==================================================

    def _atualizar_estilo_favoritos(self, marcado):

        self.bt_favoritos.setIcon(icone(
            "star-filled" if marcado else "star",
            cor=tokens.ALERTA_TEXTO, tamanho=15,
        ))
        self.bt_favoritos.setStyleSheet(f"""
            QPushButton {{
                background:{tokens.ALERTA_CLARO if marcado else tokens.CARD};
                color:{tokens.ALERTA_TEXTO};
                border:1.5px solid {tokens.ALERTA if marcado else tokens.BORDA};
                border-radius:{tokens.RADIUS_SM}px;
                padding:0 16px; font-size:13px; font-weight:bold;
            }}
        """)

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

        # sequencia: cada busca ganha um numero crescente -- a resposta
        # so' e' aplicada se ainda for a busca mais recente. Sem isso,
        # duas buscas assincronas em voo (usuario digitou nova letra
        # antes da resposta da anterior voltar) podiam se cruzar e o
        # resultado ERRADO (de uma busca antiga) sobrescrever o certo,
        # so' por ter chegado depois pela rede.
        self._busca_sequencia += 1

        # nao limpa/esconde a lista atual aqui de proposito -- deixa o
        # resultado anterior visivel ate' o novo chegar, em vez de
        # piscar a lista vazia a cada tecla (a resposta normalmente
        # volta rapido; se demorar, a lista antiga continua navegavel
        # em vez de sumir sem motivo).

        rodar_em_thread(
            self,
            _executar_pesquisa,
            self._busca_sequencia,
            termo,
            self.bt_favoritos.isChecked(),
            ao_sucesso=self._ao_busca_sucesso,
            ao_erro=self._ao_busca_erro,
        )

    def _ao_busca_sucesso(self, resultado):

        sequencia, termo, produtos = resultado

        if sequencia != self._busca_sequencia:
            return  # resposta de uma busca ja' superada, ignora

        self.lista.clear()

        for produto in produtos:

            item = QListWidgetItem()
            widget = ItemResultado(produto)
            widget.favorito_alterado.connect(self.executar_busca)

            item.setSizeHint(widget.sizeHint())
            item.setData(Qt.UserRole, produto)

            self.lista.addItem(item)
            self.lista.setItemWidget(item, widget)

        if self.lista.count() > 0:
            self.lista.setCurrentRow(0)

        # forca reaplicar o destaque agora que todo widget ja esta
        # de fato anexado -- addItem() do primeiro item dispara
        # currentRowChanged(0) ANTES do setItemWidget() rodar pra
        # essa linha (o widget ainda nao existe nesse instante), entao
        # so contar com o sinal perde o destaque da linha 0.
        self._destacar_linha_atual(self.lista.currentRow())

        self.lista.setVisible(self.lista.count() > 0)
        self.lbl_vazio.setVisible(self.lista.count() == 0)

        if self.lista.count() == 0:
            if self.bt_favoritos.isChecked():
                self.lbl_vazio.setText(
                    "Nenhum produto favorito encontrado.\n"
                    "Marque produtos como favoritos clicando na estrela."
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

    def _ao_busca_erro(self, erro):
        # erro nao passa pelo guard de sequencia (ver _ao_busca_sucesso)
        # de proposito -- um erro de rede importa mostrar mesmo que uma
        # busca mais nova ja tenha sido disparada, ela ainda nao voltou
        self.lista.clear()
        self.lista.setVisible(False)
        self.lbl_vazio.setText(f"Não foi possível buscar.\n{erro}")
        self.lbl_vazio.setVisible(True)

    # ==================================================

    def _destacar_linha_atual(self, linha_atual):

        for indice in range(self.lista.count()):

            item = self.lista.item(indice)
            widget = self.lista.itemWidget(item)

            if widget:
                widget.destacar(indice == linha_atual)

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
