from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QTextEdit,
    QDoubleSpinBox,
    QSpinBox,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
)


class CadastroProdutoWindow(QDialog):

    def __init__(self, produto=None):
        super().__init__()

        self.produto = produto

        if produto:
            self.setWindowTitle("Editar Produto")
        else:
            self.setWindowTitle("Novo Produto")

        self.resize(700, 600)

        layout = QVBoxLayout(self)

        titulo = QLabel("CADASTRO DE PRODUTO")

        titulo.setAlignment(Qt.AlignCenter)

        titulo.setStyleSheet("""
            font-size:22px;
            font-weight:bold;
        """)

        layout.addWidget(titulo)

        formulario = QGridLayout()

        # ==========================================
        # Código
        # ==========================================

        formulario.addWidget(QLabel("Código"), 0, 0)

        self.codigo = QLineEdit()

        formulario.addWidget(self.codigo, 0, 1)

        # ==========================================
        # Código de Barras
        # ==========================================

        formulario.addWidget(
            QLabel("Código de Barras"),
            1,
            0,
        )

        self.codigo_barras = QLineEdit()

        formulario.addWidget(
            self.codigo_barras,
            1,
            1,
        )

        # ==========================================
        # Nome
        # ==========================================

        formulario.addWidget(QLabel("Nome"), 2, 0)

        self.nome = QLineEdit()

        formulario.addWidget(self.nome, 2, 1)

        # ==========================================
        # Categoria
        # ==========================================

        formulario.addWidget(
            QLabel("Categoria"),
            3,
            0,
        )

        self.categoria = QLineEdit()

        formulario.addWidget(
            self.categoria,
            3,
            1,
        )

        # ==========================================
        # Unidade
        # ==========================================

        formulario.addWidget(
            QLabel("Unidade"),
            4,
            0,
        )

        self.unidade = QLineEdit()

        self.unidade.setText("UN")

        formulario.addWidget(
            self.unidade,
            4,
            1,
        )

        layout.addLayout(formulario)

        # ==========================================
        # Preço de Custo
        # ==========================================

        formulario2 = QGridLayout()

        formulario2.addWidget(QLabel("Preço de Custo"), 0, 0)

        self.preco_custo = QDoubleSpinBox()

        self.preco_custo.setMaximum(999999.99)
        self.preco_custo.setDecimals(2)
        self.preco_custo.setPrefix("R$ ")

        formulario2.addWidget(
            self.preco_custo,
            0,
            1,
        )

        # ==========================================
        # Preço de Venda
        # ==========================================

        formulario2.addWidget(QLabel("Preço de Venda"), 1, 0)

        self.preco_venda = QDoubleSpinBox()

        self.preco_venda.setMaximum(999999.99)
        self.preco_venda.setDecimals(2)
        self.preco_venda.setPrefix("R$ ")

        formulario2.addWidget(
            self.preco_venda,
            1,
            1,
        )

        # ==========================================
        # Estoque
        # ==========================================

        formulario2.addWidget(QLabel("Estoque"), 2, 0)

        self.estoque = QSpinBox()

        self.estoque.setMaximum(999999)

        formulario2.addWidget(
            self.estoque,
            2,
            1,
        )

        # ==========================================
        # Estoque Mínimo
        # ==========================================

        formulario2.addWidget(
            QLabel("Estoque Mínimo"),
            3,
            0,
        )

        self.estoque_minimo = QSpinBox()

        self.estoque_minimo.setMaximum(999999)

        formulario2.addWidget(
            self.estoque_minimo,
            3,
            1,
        )

        layout.addLayout(formulario2)

        # ==========================================
        # Descrição
        # ==========================================

        layout.addWidget(
            QLabel("Descrição")
        )

        self.descricao = QTextEdit()

        self.descricao.setMinimumHeight(120)

        layout.addWidget(self.descricao)

        # ==========================================
        # Botões
        # ==========================================

        botoes = QHBoxLayout()

        self.bt_cancelar = QPushButton("Cancelar")

        self.bt_salvar = QPushButton("Salvar")

        self.bt_salvar.setStyleSheet("""
            QPushButton{
                background:#2E7D32;
                color:white;
                font-weight:bold;
            }

            QPushButton:hover{
                background:#1B5E20;
            }
        """)

        botoes.addStretch()

        botoes.addWidget(self.bt_cancelar)

        botoes.addWidget(self.bt_salvar)

        layout.addLayout(botoes)

        self.bt_cancelar.clicked.connect(
            self.reject
        )

        self.bt_salvar.clicked.connect(
            self.salvar
        )

        # ==========================================
        # PREENCHER DADOS (EDIÇÃO)
        # ==========================================

        if self.produto:
            self.preencher_campos()
            self.codigo.setFocus()

    # ==========================================
    # PREENCHER CAMPOS (EDIÇÃO)
    # ==========================================

    def preencher_campos(self):

        if not self.produto:
            return

        self.codigo.setText(str(self.produto["codigo"]))
        self.codigo_barras.setText(
            self.produto.get("codigo_barras") or ""
        )
        self.nome.setText(self.produto["nome"])
        self.categoria.setText(
            self.produto.get("categoria") or ""
        )
        self.unidade.setText(
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
            self.produto["estoque_minimo"]
        )

        self.descricao.setPlainText(
            self.produto.get("descricao") or ""
        )

    # ==========================================
    # VALIDAR E SALVAR
    # ==========================================

    def salvar(self):

        if self.codigo.text().strip() == "":
            QMessageBox.warning(
                self,
                "Aviso",
                "Informe o código."
            )
            self.codigo.setFocus()
            return

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

        return {

            "codigo": self.codigo.text(),

            "codigo_barras": self.codigo_barras.text(),

            "nome": self.nome.text(),

            "descricao": self.descricao.toPlainText(),

            "categoria": self.categoria.text(),

            "unidade": self.unidade.text(),

            "preco_custo": float(
                self.preco_custo.value()
            ),

            "preco_venda": float(
                self.preco_venda.value()
            ),

            "estoque": self.estoque.value(),

            "estoque_minimo": self.estoque_minimo.value(),
        }