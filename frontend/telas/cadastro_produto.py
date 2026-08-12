from datetime import datetime

from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QPushButton,
    QCheckBox,
    QVBoxLayout,
    QHBoxLayout,
    QInputDialog,
    QFileDialog,
)

import base64

from services.ean_lookup import buscar_produto_externo
from services.categoria_service import listar_categorias, criar_categoria
from services.produto_service import obter_foto_produto


class CadastroProdutoWindow(QDialog):

    def __init__(self, produto=None, codigo_sugerido=None):
        super().__init__()

        self.produto = produto
        self.imagem_bytes = None
        self.modo_venda = "UN"

        self.setFixedSize(920, 640)
        self.setStyleSheet("background:white;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ======================
        # CABEÇALHO
        # ======================

        cabecalho = QHBoxLayout()
        cabecalho.setContentsMargins(30, 20, 30, 20)

        icone = QLabel("🛍️")
        icone.setFixedSize(44, 44)
        icone.setAlignment(Qt.AlignCenter)
        icone.setStyleSheet("""
            background:#202225;
            border-radius:12px;
            font-size:20px;
        """)

        col_titulo = QVBoxLayout()
        col_titulo.setSpacing(0)

        titulo_texto = "EDITAR PRODUTO" if produto else "NOVO PRODUTO"

        titulo = QLabel(titulo_texto)
        titulo.setStyleSheet(
            "background:transparent; font-size:18px; "
            "font-weight:bold; color:#202225;"
        )

        subtitulo = QLabel("Preencha os dados básicos para começar")
        subtitulo.setStyleSheet(
            "background:transparent; font-size:11px; color:gray;"
        )

        col_titulo.addWidget(titulo)
        col_titulo.addWidget(subtitulo)

        self.bt_cancelar_topo = QPushButton("✕ Cancelar")
        self.bt_cancelar_topo.setStyleSheet("""
            QPushButton {
                background:#f4f5f7;
                color:#202225;
                border-radius:8px;
                padding:8px 14px;
            }
            QPushButton:hover {
                background:#e8e8e8;
            }
        """)
        self.bt_cancelar_topo.clicked.connect(self.reject)

        self.favorito = QCheckBox("★ Favorito")
        self.favorito.setToolTip(
            "Produtos favoritos ficam em destaque na busca do PDV"
        )
        self.favorito.setStyleSheet("""
            QCheckBox {
                background:transparent; font-size:12px;
                font-weight:bold; color:#B45309;
            }
        """)

        cabecalho.addWidget(icone)
        cabecalho.addSpacing(12)
        cabecalho.addLayout(col_titulo)
        cabecalho.addStretch()
        cabecalho.addWidget(self.favorito)
        cabecalho.addSpacing(12)
        cabecalho.addWidget(self.bt_cancelar_topo)

        layout.addLayout(cabecalho)

        # ======================
        # CORPO (2 colunas)
        # ======================

        corpo = QHBoxLayout()
        corpo.setContentsMargins(30, 10, 30, 10)
        corpo.setSpacing(40)

        # ---- coluna esquerda ----

        esquerda = QVBoxLayout()
        esquerda.setSpacing(14)

        esquerda.addWidget(
            self._titulo_secao("INFORMAÇÕES BÁSICAS", "#1565C0")
        )

        esquerda.addWidget(
            self._rotulo("CÓDIGO DE BARRAS (opcional)")
        )

        linha_codigo = QHBoxLayout()

        self.codigo_barras = QLineEdit()
        self.codigo_barras.setPlaceholderText("Bipar ou digitar...")
        self.codigo_barras.setMinimumHeight(42)
        self.codigo_barras.setStyleSheet(self._estilo_input())
        self.codigo_barras.returnPressed.connect(self.buscar_automatico)
        self.codigo_barras.textChanged.connect(
            self.agendar_busca_automatica
        )

        self.timer_busca_automatica = QTimer(self)
        self.timer_busca_automatica.setSingleShot(True)
        self.timer_busca_automatica.timeout.connect(
            lambda: self.buscar_automatico(silencioso=True)
        )

        self.bt_buscar = QPushButton("✨")
        self.bt_buscar.setFixedSize(42, 42)
        self.bt_buscar.setToolTip("Buscar produto pelo código")
        self.bt_buscar.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                border-radius:10px;
                font-size:16px;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
        """)
        self.bt_buscar.clicked.connect(
            lambda: self.buscar_automatico(silencioso=False)
        )

        self.bt_camera = QPushButton("📷")
        self.bt_camera.setFixedSize(42, 42)
        self.bt_camera.setToolTip("Ler código pela câmera")
        self.bt_camera.setStyleSheet("""
            QPushButton {
                background:#7b3fe4;
                border-radius:10px;
                font-size:16px;
            }
            QPushButton:hover {
                background:#652fc7;
            }
        """)
        self.bt_camera.clicked.connect(self.leitor_camera_indisponivel)

        linha_codigo.addWidget(self.codigo_barras)
        linha_codigo.addWidget(self.bt_buscar)
        linha_codigo.addWidget(self.bt_camera)

        esquerda.addLayout(linha_codigo)

        esquerda.addWidget(self._rotulo("NOME DO PRODUTO"))

        self.nome = QLineEdit()
        self.nome.setPlaceholderText("Ex: Coca-Cola Lata 350ml")
        self.nome.setMinimumHeight(42)
        self.nome.setStyleSheet(self._estilo_input())

        esquerda.addWidget(self.nome)

        esquerda.addWidget(self._rotulo("CATEGORIA DO PRODUTO"))

        linha_categoria = QHBoxLayout()

        self.categoria = QComboBox()
        self.categoria.setEditable(True)
        self.categoria.setMinimumHeight(42)
        self.categoria.setStyleSheet("""
            QComboBox {
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 14px;
                color: #202225;
                background: white;
            }
        """)
        self._carregar_categorias()

        self.bt_nova_categoria = QPushButton("+")
        self.bt_nova_categoria.setFixedSize(42, 42)
        self.bt_nova_categoria.setToolTip("Criar nova categoria")
        self.bt_nova_categoria.setStyleSheet("""
            QPushButton {
                background:#f4f5f7;
                color:#202225;
                border-radius:10px;
                font-size:18px;
                font-weight:bold;
            }
            QPushButton:hover {
                background:#e8e8e8;
            }
        """)
        self.bt_nova_categoria.clicked.connect(self.criar_nova_categoria)

        linha_categoria.addWidget(self.categoria)
        linha_categoria.addWidget(self.bt_nova_categoria)

        esquerda.addLayout(linha_categoria)

        esquerda.addStretch()

        # ---- coluna direita ----

        direita = QVBoxLayout()
        direita.setSpacing(14)

        direita.addWidget(
            self._titulo_secao("VALORES E DISPONIBILIDADE", "#2E7D32")
        )

        linha_preco_modo = QHBoxLayout()
        linha_preco_modo.setSpacing(16)

        col_preco = QVBoxLayout()
        col_preco.addWidget(self._rotulo("PREÇO DE VENDA"))
        self.preco_venda = QDoubleSpinBox()
        self.preco_venda.setMaximum(999999.99)
        self.preco_venda.setDecimals(2)
        self.preco_venda.setPrefix("R$ ")
        self.preco_venda.setMinimumHeight(42)
        self.preco_venda.setStyleSheet(self._estilo_input("QDoubleSpinBox"))
        col_preco.addWidget(self.preco_venda)

        col_modo = QVBoxLayout()
        col_modo.addWidget(self._rotulo("MODO DE VENDA"))

        linha_modo = QHBoxLayout()
        linha_modo.setSpacing(4)

        self.botoes_modo = {}

        for rotulo, valor in [
            ("UNID", "UN"), ("PESO", "KG"), ("LITRO", "L"),
        ]:
            bt = QPushButton(rotulo)
            bt.setCheckable(True)
            bt.setMinimumHeight(42)
            bt.clicked.connect(
                lambda checked, v=valor: self.selecionar_modo(v)
            )
            self.botoes_modo[valor] = bt
            linha_modo.addWidget(bt)

        col_modo.addLayout(linha_modo)

        linha_preco_modo.addLayout(col_preco)
        linha_preco_modo.addLayout(col_modo)

        direita.addLayout(linha_preco_modo)

        linha_custo_estoque = QHBoxLayout()
        linha_custo_estoque.setSpacing(16)

        col_custo = QVBoxLayout()
        col_custo.addWidget(self._rotulo("CUSTO COMPRA (R$)"))
        self.preco_custo = QDoubleSpinBox()
        self.preco_custo.setMaximum(999999.99)
        self.preco_custo.setDecimals(2)
        self.preco_custo.setMinimumHeight(42)
        self.preco_custo.setStyleSheet(self._estilo_input("QDoubleSpinBox"))
        col_custo.addWidget(self.preco_custo)

        col_estoque = QVBoxLayout()
        col_estoque.addWidget(self._rotulo("ESTOQUE INICIAL"))
        self.estoque = QSpinBox()
        self.estoque.setMaximum(999999)
        self.estoque.setMinimumHeight(42)
        self.estoque.setStyleSheet(self._estilo_input("QSpinBox"))
        col_estoque.addWidget(self.estoque)

        linha_custo_estoque.addLayout(col_custo)
        linha_custo_estoque.addLayout(col_estoque)

        direita.addLayout(linha_custo_estoque)

        col_estoque_minimo = QVBoxLayout()
        col_estoque_minimo.addWidget(
            self._rotulo("ESTOQUE MÍNIMO (ALERTA)")
        )
        self.estoque_minimo = QSpinBox()
        self.estoque_minimo.setMaximum(999999)
        self.estoque_minimo.setMinimumHeight(42)
        self.estoque_minimo.setStyleSheet(
            self._estilo_input("QSpinBox")
        )
        col_estoque_minimo.addWidget(self.estoque_minimo)

        direita.addLayout(col_estoque_minimo)

        direita.addWidget(self._rotulo("FOTO DO PRODUTO"))

        linha_foto = QHBoxLayout()

        self.lbl_foto = QLabel("📷")
        self.lbl_foto.setFixedSize(70, 70)
        self.lbl_foto.setAlignment(Qt.AlignCenter)
        self.lbl_foto.setStyleSheet("""
            background:#eef0f3;
            border-radius:10px;
            font-size:26px;
        """)

        self.bt_adicionar_imagem = QPushButton("Adicionar Imagem")
        self.bt_adicionar_imagem.setMinimumHeight(70)
        self.bt_adicionar_imagem.setStyleSheet("""
            QPushButton {
                background:#f4f5f7;
                color:#202225;
                border-radius:10px;
            }
            QPushButton:hover {
                background:#e8e8e8;
            }
        """)
        self.bt_adicionar_imagem.clicked.connect(
            self.adicionar_imagem
        )

        linha_foto.addWidget(self.lbl_foto)
        linha_foto.addWidget(self.bt_adicionar_imagem, stretch=1)

        direita.addLayout(linha_foto)

        direita.addStretch()

        corpo.addLayout(esquerda, stretch=1)
        corpo.addLayout(direita, stretch=1)

        layout.addLayout(corpo)

        # ======================
        # RODAPÉ
        # ======================

        rodape = QHBoxLayout()
        rodape.setContentsMargins(30, 16, 30, 24)

        self.bt_cancelar = QPushButton("Cancelar e sair")
        self.bt_cancelar.setStyleSheet("""
            QPushButton {
                background:transparent;
                color:gray;
                border:none;
                font-size:13px;
            }
            QPushButton:hover {
                color:#202225;
            }
        """)
        self.bt_cancelar.clicked.connect(self.reject)

        texto_salvar = (
            "Salvar Alterações" if produto else "Cadastrar Produto →"
        )

        self.bt_salvar = QPushButton(texto_salvar)
        self.bt_salvar.setMinimumHeight(48)
        self.bt_salvar.setMinimumWidth(220)
        self.bt_salvar.setStyleSheet("""
            QPushButton {
                background:#2E7D32;
                color:white;
                font-weight:bold;
                border-radius:10px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background:#1B5E20;
            }
        """)
        self.bt_salvar.clicked.connect(self.salvar)

        rodape.addWidget(self.bt_cancelar)
        rodape.addStretch()
        rodape.addWidget(self.bt_salvar)

        layout.addLayout(rodape)

        self.selecionar_modo("UN")

        self.codigo_barras.returnPressed.connect(self.nome.setFocus)

        if self.produto:
            self.preencher_campos()
            self.codigo_barras.setFocus()
        else:
            self.codigo_barras.setFocus()

    # ==========================================
    # HELPERS DE ESTILO
    # ==========================================

    def _titulo_secao(self, texto, cor):
        lbl = QLabel(texto)
        lbl.setStyleSheet(f"""
            background:transparent;
            color:{cor};
            font-size:12px;
            font-weight:bold;
            border-left: 3px solid {cor};
            padding-left: 8px;
        """)
        return lbl

    def _rotulo(self, texto):
        lbl = QLabel(texto)
        lbl.setStyleSheet(
            "background:transparent; font-size:10px; "
            "font-weight:bold; color:gray;"
        )
        return lbl

    def _estilo_input(self, widget="QLineEdit"):
        return f"""
            {widget} {{
                border: 1px solid #cccccc;
                border-radius: 8px;
                padding: 0 12px;
                font-size: 14px;
                color: #202225;
                background: white;
            }}
            {widget}:focus {{
                border: 1px solid #2E7D32;
            }}
        """

    # ==========================================
    # CATEGORIAS
    # ==========================================

    def _carregar_categorias(self):

        categorias = listar_categorias()

        self.categoria.clear()

        for c in categorias:
            if c.get("ativo", True):
                self.categoria.addItem(c["nome"])

        self.categoria.setCurrentText("")

    def criar_nova_categoria(self):

        nome, ok = QInputDialog.getText(
            self,
            "Nova Categoria",
            "Nome da nova categoria:"
        )

        if not ok or not nome.strip():
            return

        nome = nome.strip()

        response = criar_categoria(nome)

        if response.status_code in (200, 201):

            if self.categoria.findText(nome) < 0:
                self.categoria.addItem(nome)

            self.categoria.setCurrentText(nome)

        else:

            try:
                erro = response.json()["detail"]
            except Exception:
                erro = response.text

            QMessageBox.critical(self, "Erro", str(erro))

    # ==========================================
    # MODO DE VENDA (UNID / PESO / LITRO)
    # ==========================================

    def selecionar_modo(self, valor):

        self.modo_venda = valor

        for chave, botao in self.botoes_modo.items():

            selecionado = chave == valor
            botao.setChecked(selecionado)

            botao.setStyleSheet(f"""
                QPushButton {{
                    background: {"#202225" if selecionado else "#f4f5f7"};
                    color: {"white" if selecionado else "#202225"};
                    border-radius: 8px;
                    font-weight: bold;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background: {"#33363b" if selecionado else "#e8e8e8"};
                }}
            """)

    # ==========================================
    # BUSCA AUTOMÁTICA PELO CÓDIGO DE BARRAS
    # ==========================================

    def agendar_busca_automatica(self, texto):

        self.timer_busca_automatica.stop()

        # so dispara sozinho com tamanho de codigo de barras de
        # verdade, pra nao ficar buscando a cada digito
        if len(texto.strip()) >= 8:
            self.timer_busca_automatica.start(400)

    def buscar_automatico(self, silencioso=False):

        codigo = self.codigo_barras.text().strip()

        if not codigo:
            if not silencioso:
                QMessageBox.information(
                    self,
                    "Buscar produto",
                    "Informe um código de barras para buscar."
                )
            return

        self.bt_buscar.setEnabled(False)
        self.bt_buscar.setText("...")
        QApplication.processEvents()

        resultado = buscar_produto_externo(codigo)

        self.bt_buscar.setEnabled(True)
        self.bt_buscar.setText("✨")

        if resultado is None:

            if not silencioso:
                QMessageBox.information(
                    self,
                    "Buscar produto",
                    "Produto não encontrado na base pública "
                    "(Open Food Facts). Cadastre os dados manualmente."
                )
            return

        self.nome.setText(resultado["nome"])

        if resultado["imagem_bytes"]:

            self.imagem_bytes = resultado["imagem_bytes"]

            pixmap = QPixmap()
            pixmap.loadFromData(self.imagem_bytes)
            self.lbl_foto.setText("")
            self.lbl_foto.setPixmap(
                pixmap.scaled(
                    70, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
            )

    def leitor_camera_indisponivel(self):
        QMessageBox.information(
            self,
            "Leitura por câmera",
            "A leitura de código de barras pela câmera ainda não "
            "foi implementada. Use um leitor USB/bluetooth "
            "(que digita como teclado) ou digite o código."
        )

    def adicionar_imagem(self):

        caminho, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem",
            "",
            "Imagens (*.png *.jpg *.jpeg *.bmp *.webp)",
        )

        if not caminho:
            return

        try:
            with open(caminho, "rb") as arquivo:
                self.imagem_bytes = arquivo.read()
        except OSError as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        self._exibir_imagem(self.imagem_bytes)

    def _exibir_imagem(self, imagem_bytes):

        pixmap = QPixmap()
        pixmap.loadFromData(imagem_bytes)

        if pixmap.isNull():
            QMessageBox.warning(
                self,
                "Imagem inválida",
                "Não foi possível abrir essa imagem."
            )
            return

        self.lbl_foto.setText("")
        self.lbl_foto.setPixmap(
            pixmap.scaled(
                70, 70, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        )

    # ==========================================
    # PREENCHER CAMPOS (EDIÇÃO)
    # ==========================================

    def preencher_campos(self):

        if not self.produto:
            return

        self.codigo_barras.setText(
            self.produto.get("codigo_barras") or ""
        )
        self.nome.setText(self.produto["nome"])
        self.categoria.setCurrentText(
            self.produto.get("categoria") or ""
        )

        self.selecionar_modo(
            self.produto.get("unidade") or "UN"
        )

        self.preco_custo.setValue(
            float(self.produto["preco_custo"])
        )

        self.preco_venda.setValue(
            float(self.produto["preco_venda"])
        )

        self.estoque.setValue(
            self.produto["estoque"]
        )

        self.estoque_minimo.setValue(
            self.produto.get("estoque_minimo", 0)
        )

        self.favorito.setChecked(self.produto.get("favorito", False))

        if self.produto.get("tem_foto"):

            foto_bytes = obter_foto_produto(self.produto["id"])

            if foto_bytes:
                pixmap = QPixmap()
                pixmap.loadFromData(foto_bytes)
                self.lbl_foto.setText("")
                self.lbl_foto.setPixmap(
                    pixmap.scaled(
                        70,
                        70,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )

    # ==========================================
    # VALIDAR E SALVAR
    # ==========================================

    def salvar(self):

        if self.nome.text().strip() == "":
            QMessageBox.warning(
                self,
                "Aviso",
                "Informe o nome do produto."
            )
            self.nome.setFocus()
            return

        if self.preco_venda.value() <= 0:
            QMessageBox.warning(
                self,
                "Aviso",
                "Informe um preço de venda válido."
            )
            self.preco_venda.setFocus()
            return

        self.accept()

    # ==========================================
    # DADOS
    # ==========================================

    @property
    def dados(self):

        codigo_barras = self.codigo_barras.text().strip() or None

        if self.produto:
            codigo = self.produto["codigo"]
        elif codigo_barras:
            codigo = codigo_barras
        else:
            codigo = "PROD-" + datetime.now().strftime(
                "%Y%m%d%H%M%S%f"
            )

        foto_base64 = None

        if self.imagem_bytes:
            foto_base64 = base64.b64encode(
                self.imagem_bytes
            ).decode("ascii")

        return {

            "codigo": codigo,

            "codigo_barras": codigo_barras,

            "foto_base64": foto_base64,

            "nome": self.nome.text().strip(),

            "descricao": None,

            "categoria": self.categoria.currentText().strip() or None,

            "unidade": self.modo_venda,

            "preco_custo": float(
                self.preco_custo.value()
            ),

            "preco_venda": float(
                self.preco_venda.value()
            ),

            "estoque": self.estoque.value(),

            "estoque_minimo": self.estoque_minimo.value(),

            "favorito": self.favorito.isChecked(),
        }
