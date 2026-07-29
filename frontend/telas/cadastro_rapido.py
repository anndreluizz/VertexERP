from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QSpinBox,
    QPushButton,
    QMessageBox,
)

from services.ean_lookup import buscar_produto_externo
from services.produto_service import (
    cadastrar_produto,
    atualizar_produto,
    buscar_produto as buscar_produto_por_id,
)
from services.pdv_service import buscar_produto as buscar_produto_local
from telas.produto_criado import ProdutoCriadoDialog


class CadastroRapidoDialog(QDialog):

    def __init__(self, parent=None):

        super().__init__(parent)

        self.codigo_barras = None
        self.nome_produto = None
        self.imagem_bytes = None
        self.produto_criado = None
        self.produto_existente_id = None

        self.setWindowTitle("+ Cadastro Rápido")
        self.setFixedSize(460, 420)
        self.setStyleSheet("background:white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 26, 30, 26)
        layout.setSpacing(14)

        cabecalho = QHBoxLayout()

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo = QLabel("+ Cadastro Rápido")
        titulo.setStyleSheet(
            "background:transparent; font-size:19px; "
            "font-weight:bold; color:#202225;"
        )

        self.subtitulo = QLabel("Bipe o código para começar")
        self.subtitulo.setStyleSheet(
            "background:transparent; font-size:12px; color:gray;"
        )

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(self.subtitulo)

        bt_fechar = QPushButton("✕")
        bt_fechar.setFixedSize(28, 28)
        bt_fechar.setAutoDefault(False)
        bt_fechar.setDefault(False)
        bt_fechar.setStyleSheet("""
            QPushButton {
                background:#f0f0f0;
                border-radius:14px;
            }
            QPushButton:hover {
                background:#e0e0e0;
            }
        """)
        bt_fechar.clicked.connect(self.reject)

        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(bt_fechar)

        layout.addLayout(cabecalho)

        # ======================
        # PASSO 1: LER CÓDIGO
        # ======================

        self.passo1 = QFrame()
        p1_layout = QVBoxLayout(self.passo1)
        p1_layout.setSpacing(8)

        lbl_codigo_titulo = QLabel("CÓDIGO EAN / BARRAS")
        lbl_codigo_titulo.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:gray;"
        )

        self.campo_codigo = QLineEdit()
        self.campo_codigo.setPlaceholderText("Bipe ou digite o código...")
        self.campo_codigo.setMinimumHeight(48)
        self.campo_codigo.setStyleSheet("""
            QLineEdit {
                border: 2px solid #cccccc;
                border-radius: 10px;
                padding: 0 14px;
                font-size: 16px;
                color: #202225;
            }
            QLineEdit:focus {
                border: 2px solid #2E7D32;
            }
        """)
        self.campo_codigo.returnPressed.connect(self.buscar)
        self.campo_codigo.textChanged.connect(self.agendar_busca_automatica)

        self.timer_busca_automatica = QTimer(self)
        self.timer_busca_automatica.setSingleShot(True)
        self.timer_busca_automatica.timeout.connect(self.buscar)

        dica = QLabel(
            "+ O sistema buscará o nome e imagem automaticamente"
        )
        dica.setStyleSheet(
            "background:transparent; font-size:11px; color:gray;"
        )
        dica.setWordWrap(True)

        p1_layout.addWidget(lbl_codigo_titulo)
        p1_layout.addWidget(self.campo_codigo)
        p1_layout.addWidget(dica)
        p1_layout.addStretch()

        layout.addWidget(self.passo1)

        # ======================
        # PASSO 2: RESULTADO
        # ======================

        self.passo2 = QFrame()
        p2_layout = QVBoxLayout(self.passo2)
        p2_layout.setSpacing(12)

        resultado = QHBoxLayout()

        self.lbl_imagem = QLabel("📦")
        self.lbl_imagem.setFixedSize(70, 70)
        self.lbl_imagem.setAlignment(Qt.AlignCenter)
        self.lbl_imagem.setStyleSheet("""
            background:#eef0f3;
            border-radius:10px;
            font-size:28px;
        """)

        col_resultado = QVBoxLayout()
        col_resultado.setSpacing(0)

        self.lbl_status = QLabel("LOCALIZADO!")
        self.lbl_status.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:#2E7D32;"
        )

        self.lbl_nome = QLabel()
        self.lbl_nome.setWordWrap(True)
        self.lbl_nome.setStyleSheet(
            "background:transparent; font-size:15px; "
            "font-weight:bold; color:#202225;"
        )

        self.lbl_codigo_encontrado = QLabel()
        self.lbl_codigo_encontrado.setStyleSheet(
            "background:transparent; font-size:11px; color:gray;"
        )

        col_resultado.addWidget(self.lbl_status)
        col_resultado.addWidget(self.lbl_nome)
        col_resultado.addWidget(self.lbl_codigo_encontrado)

        resultado.addWidget(self.lbl_imagem)
        resultado.addLayout(col_resultado, stretch=1)

        p2_layout.addLayout(resultado)

        campos = QHBoxLayout()
        campos.setSpacing(16)

        col_preco = QVBoxLayout()
        lbl_preco = QLabel("PREÇO DE VENDA (R$)")
        lbl_preco.setStyleSheet(
            "background:transparent; font-size:10px; "
            "font-weight:bold; color:gray;"
        )
        self.preco = QDoubleSpinBox()
        self.preco.setMaximum(999999)
        self.preco.setDecimals(2)
        self.preco.setPrefix("R$ ")
        self.preco.setMinimumHeight(40)
        self.preco.setStyleSheet("""
            QDoubleSpinBox {
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 0 8px;
                font-size: 14px;
                color: #202225;
                background: white;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #2E7D32;
            }
        """)
        col_preco.addWidget(lbl_preco)
        col_preco.addWidget(self.preco)

        col_qtd = QVBoxLayout()
        lbl_qtd = QLabel("QTD. EM ESTOQUE")
        lbl_qtd.setStyleSheet(
            "background:transparent; font-size:10px; "
            "font-weight:bold; color:gray;"
        )
        self.quantidade = QSpinBox()
        self.quantidade.setMaximum(999999)
        self.quantidade.setMinimumHeight(40)
        self.quantidade.setStyleSheet("""
            QSpinBox {
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 0 8px;
                font-size: 14px;
                color: #202225;
                background: white;
            }
            QSpinBox:focus {
                border: 1px solid #2E7D32;
            }
        """)
        col_qtd.addWidget(lbl_qtd)
        col_qtd.addWidget(self.quantidade)

        campos.addLayout(col_preco)
        campos.addLayout(col_qtd)

        p2_layout.addLayout(campos)

        self.bt_concluir = QPushButton("CONCLUIR CADASTRO")
        self.bt_concluir.setMinimumHeight(48)
        self.bt_concluir.setAutoDefault(False)
        self.bt_concluir.setStyleSheet("""
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
        self.bt_concluir.clicked.connect(self.concluir)

        self.bt_voltar_codigo = QPushButton("Voltar e corrigir código")
        self.bt_voltar_codigo.setAutoDefault(False)
        self.bt_voltar_codigo.setStyleSheet("""
            QPushButton {
                background:transparent;
                color:gray;
                border:none;
                font-size:12px;
            }
            QPushButton:hover {
                color:#202225;
            }
        """)
        self.bt_voltar_codigo.clicked.connect(self.mostrar_passo1)

        p2_layout.addWidget(self.bt_concluir)
        p2_layout.addWidget(
            self.bt_voltar_codigo, alignment=Qt.AlignHCenter
        )

        layout.addWidget(self.passo2)

        self.mostrar_passo1()

        self.campo_codigo.setFocus()

    # ==================================================

    def mostrar_passo1(self):
        self.passo1.setVisible(True)
        self.passo2.setVisible(False)
        self.produto_existente_id = None
        self.bt_concluir.setEnabled(True)
        self.bt_concluir.setText("CONCLUIR CADASTRO")
        self.campo_codigo.setFocus()
        self.campo_codigo.selectAll()

    def mostrar_passo2(self):
        self.passo1.setVisible(False)
        self.passo2.setVisible(True)

    # ==================================================

    def agendar_busca_automatica(self, texto):

        self.timer_busca_automatica.stop()

        # so dispara sozinho se o codigo ja tem tamanho de
        # codigo de barras de verdade (EAN-8 pra cima); assim
        # nao fica buscando a cada digito enquanto a pessoa
        # ainda esta digitando um codigo curto
        if len(texto.strip()) >= 8:
            self.timer_busca_automatica.start(400)

    def buscar(self):

        codigo = self.campo_codigo.text().strip()

        if not codigo:
            return

        self.subtitulo.setText("Buscando...")
        self.campo_codigo.setEnabled(False)
        QApplication.processEvents()

        produto_local = buscar_produto_local(codigo)

        if produto_local is not None:

            self.subtitulo.setText("Bipe o código para começar")
            self.campo_codigo.setEnabled(True)

            self.mostrar_produto_ja_cadastrado(produto_local)

            return

        resultado = buscar_produto_externo(codigo)

        self.subtitulo.setText("Bipe o código para começar")
        self.campo_codigo.setEnabled(True)

        self.codigo_barras = codigo

        if resultado is None:

            self.nome_produto = None

            self.lbl_status.setText("NÃO ENCONTRADO")
            self.lbl_status.setStyleSheet(
                "background:transparent; font-size:11px; "
                "font-weight:bold; color:#C62828;"
            )
            self.lbl_nome.setText(
                "Produto não encontrado na base pública. "
                "Cadastre o nome manualmente."
            )
            self.lbl_imagem.setPixmap(QPixmap())
            self.lbl_imagem.setText("📦")

        else:

            self.nome_produto = resultado["nome"]

            self.lbl_status.setText("LOCALIZADO!")
            self.lbl_status.setStyleSheet(
                "background:transparent; font-size:11px; "
                "font-weight:bold; color:#2E7D32;"
            )
            self.lbl_nome.setText(self.nome_produto)

            self.imagem_bytes = resultado["imagem_bytes"]

            if resultado["imagem_bytes"]:
                pixmap = QPixmap()
                pixmap.loadFromData(resultado["imagem_bytes"])
                self.lbl_imagem.setText("")
                self.lbl_imagem.setPixmap(
                    pixmap.scaled(
                        70,
                        70,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
            else:
                self.lbl_imagem.setPixmap(QPixmap())
                self.lbl_imagem.setText("📦")

        self.lbl_codigo_encontrado.setText(codigo)

        self.mostrar_passo2()

    def mostrar_produto_ja_cadastrado(self, produto):

        self.codigo_barras = produto["codigo"]
        self.nome_produto = None
        self.imagem_bytes = None
        self.produto_existente_id = produto["id"]

        self.lbl_status.setText("JÁ CADASTRADO")
        self.lbl_status.setStyleSheet(
            "background:transparent; font-size:11px; "
            "font-weight:bold; color:#1565C0;"
        )
        self.lbl_nome.setText(
            f"{produto['nome']} já está cadastrado. Ajuste o preço "
            f"e/ou a quantidade em estoque abaixo, se precisar."
        )
        self.lbl_imagem.setPixmap(QPixmap())
        self.lbl_imagem.setText("📦")
        self.lbl_codigo_encontrado.setText(produto["codigo"])

        self.preco.setValue(float(produto["preco"]))
        self.quantidade.setValue(produto["estoque"])

        self.bt_concluir.setEnabled(True)
        self.bt_concluir.setText("ATUALIZAR PRODUTO")

        self.mostrar_passo2()

    # ==================================================

    def concluir(self):

        if self.produto_existente_id:
            self.atualizar_existente()
            return

        nome = self.nome_produto

        if not nome:

            nome, ok = (
                self.lbl_nome.text(),
                True,
            )

            from PySide6.QtWidgets import QInputDialog

            nome, ok = QInputDialog.getText(
                self,
                "Nome do produto",
                "Produto não encontrado automaticamente. "
                "Digite o nome:",
            )

            if not ok or not nome.strip():
                return

            nome = nome.strip()

        foto_base64 = None

        if self.imagem_bytes:
            import base64
            foto_base64 = base64.b64encode(
                self.imagem_bytes
            ).decode("ascii")

        dados = {
            "codigo": self.codigo_barras,
            "codigo_barras": self.codigo_barras,
            "nome": nome,
            "categoria": None,
            "foto_base64": foto_base64,
            "preco_custo": 0,
            "preco_venda": self.preco.value(),
            "estoque": self.quantidade.value(),
            "estoque_minimo": 0,
            "unidade": "UN",
        }

        response = cadastrar_produto(dados)

        if response.status_code == 201:

            produto_criado = response.json()

            sucesso = ProdutoCriadoDialog(
                produto_criado["nome"],
                float(produto_criado["preco_venda"]),
                self.imagem_bytes,
                self,
            )
            sucesso.exec()

            if sucesso.editar_solicitado:

                from telas.cadastro_produto import CadastroProdutoWindow

                tela_edicao = CadastroProdutoWindow(produto_criado)

                if tela_edicao.exec() == QDialog.Accepted:
                    atualizar_produto(
                        produto_criado["id"],
                        tela_edicao.dados,
                    )

            self.produto_criado = produto_criado

            self.accept()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    def atualizar_existente(self):

        produto_atual = buscar_produto_por_id(self.produto_existente_id)

        if produto_atual is None:
            QMessageBox.critical(
                self,
                "Erro",
                "Não foi possível carregar o produto para atualizar.",
            )
            return

        dados = {
            "codigo": produto_atual["codigo"],
            "nome": produto_atual["nome"],
            "descricao": produto_atual.get("descricao"),
            "codigo_barras": produto_atual.get("codigo_barras"),
            "categoria": produto_atual.get("categoria"),
            "unidade": produto_atual.get("unidade", "UN"),
            "preco_custo": float(produto_atual.get("preco_custo") or 0),
            "preco_venda": self.preco.value(),
            "estoque": self.quantidade.value(),
            "estoque_minimo": produto_atual.get("estoque_minimo", 0),
            "ativo": produto_atual.get("ativo", True),
        }

        response = atualizar_produto(self.produto_existente_id, dados)

        if response.status_code == 200:

            QMessageBox.information(
                self,
                "Sucesso",
                "Produto atualizado com sucesso!",
            )

            self.accept()

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))
