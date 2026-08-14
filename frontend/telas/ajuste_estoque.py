from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QMessageBox,
    QDialog,
    QTableWidgetItem,
)

from services.produto_service import listar_produtos
from services.estoque_service import listar_movimentos, ajustar_estoque
from widgets.dialogs.pesquisa_window import PesquisaWindow
from widgets.tables.standard_table import StandardTable
from design import tokens


class AjusteEstoque(QWidget):

    def __init__(self):
        super().__init__()

        self.produto_id = None

        layout = QVBoxLayout(self)

        titulo = QLabel("AJUSTE DE ESTOQUE")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size:24px; font-weight:bold;")
        layout.addWidget(titulo)

        # ==========================================
        # PRODUTO
        # ==========================================
        produto_layout = QHBoxLayout()

        produto_layout.addWidget(QLabel("Produto"))

        self.produto = QLineEdit()
        self.produto.setReadOnly(True)
        self.produto.setPlaceholderText("Selecione um produto...")

        self.bt_produto = QPushButton("Pesquisar")

        produto_layout.addWidget(self.produto)
        produto_layout.addWidget(self.bt_produto)

        layout.addLayout(produto_layout)

        # ==========================================
        # TIPO / QUANTIDADE / MOTIVO
        # ==========================================
        dados_layout = QHBoxLayout()

        dados_layout.addWidget(QLabel("Tipo"))

        self.tipo = QComboBox()
        self.tipo.addItems(["Entrada", "Saída"])

        dados_layout.addWidget(self.tipo)

        dados_layout.addWidget(QLabel("Quantidade"))

        self.quantidade = QLineEdit()
        self.quantidade.setPlaceholderText("0")
        self.quantidade.setMaximumWidth(100)

        dados_layout.addWidget(self.quantidade)

        dados_layout.addWidget(QLabel("Motivo"))

        self.motivo = QLineEdit()
        self.motivo.setPlaceholderText("Ex.: inventário, quebra, correção...")

        dados_layout.addWidget(self.motivo)

        self.bt_registrar = QPushButton("Registrar Ajuste")

        self.bt_registrar.setStyleSheet(f"""
            QPushButton{{
                background:{tokens.SECUNDARIA};
                color:{tokens.TEXTO_CLARO};
                font-weight:bold;
                padding:6px 16px;
            }}
            QPushButton:hover{{
                background:{tokens.SECUNDARIA_HOVER};
            }}
        """)

        dados_layout.addWidget(self.bt_registrar)

        layout.addLayout(dados_layout)

        # ==========================================
        # HISTÓRICO
        # ==========================================
        layout.addWidget(QLabel("Histórico de Movimentações"))

        self.tabela = StandardTable(
            ["Data", "Produto", "Tipo", "Quantidade", "Motivo"]
        )

        layout.addWidget(self.tabela)

        # ==========================================
        # EVENTOS
        # ==========================================
        self.bt_produto.clicked.connect(self.pesquisar_produto)
        self.bt_registrar.clicked.connect(self.registrar_ajuste)

        self.carregar()

    # ==========================================
    # PESQUISAR PRODUTO
    # ==========================================
    def pesquisar_produto(self):
        produtos = listar_produtos()

        tela = PesquisaWindow(
            titulo="Pesquisar Produto",
            colunas=["Código", "Nome", "Categoria", "Estoque"],
            campos=["codigo", "nome", "categoria", "estoque"],
            dados=produtos,
            chave_pesquisa="nome",
        )

        if tela.exec() != QDialog.Accepted:
            return

        self.produto_id = tela.selecionado["id"]

        self.produto.setText(
            f"{tela.selecionado['nome']} "
            f"(estoque atual: {tela.selecionado['estoque']})"
        )

    # ==========================================
    # CARREGAR HISTÓRICO
    # ==========================================
    def carregar(self):
        self.produtos_map = {
            produto["id"]: produto["nome"] for produto in listar_produtos()
        }

        self.movimentos = listar_movimentos()
        self.preencher_tabela(self.movimentos)

    def preencher_tabela(self, movimentos):
        self.tabela.setRowCount(len(movimentos))

        for linha, mov in enumerate(movimentos):
            data = datetime.fromisoformat(mov["data"]).strftime("%d/%m/%Y %H:%M")

            self.tabela.setItem(linha, 0, QTableWidgetItem(data))

            self.tabela.setItem(
                linha,
                1,
                QTableWidgetItem(
                    self.produtos_map.get(
                        mov["produto_id"], f"#{mov['produto_id']}"
                    )
                ),
            )

            self.tabela.setItem(
                linha,
                2,
                QTableWidgetItem(
                    "Entrada" if mov["tipo"] == "ENTRADA" else "Saída"
                ),
            )

            self.tabela.setItem(
                linha, 3, QTableWidgetItem(str(mov["quantidade"]))
            )

            self.tabela.setItem(
                linha, 4, QTableWidgetItem(mov.get("motivo") or "")
            )

    # ==========================================
    # REGISTRAR AJUSTE
    # ==========================================
    def registrar_ajuste(self):
        if self.produto_id is None:
            QMessageBox.warning(self, "Aviso", "Selecione um produto.")
            return

        try:
            quantidade = int(self.quantidade.text())
            if quantidade <= 0:
                raise ValueError

        except ValueError:
            QMessageBox.warning(
                self, "Aviso", "Informe uma quantidade válida."
            )
            return

        dados = {
            "produto_id": self.produto_id,
            "tipo": "ENTRADA" if self.tipo.currentText() == "Entrada" else "SAIDA",
            "quantidade": quantidade,
            "motivo": self.motivo.text() or None,
        }

        response = ajustar_estoque(dados)

        if response.status_code == 201:
            QMessageBox.information(
                self, "Sucesso", "Ajuste registrado com sucesso."
            )
            self._limpar()
            self.carregar()
        else:
            self._exibir_erro(response)

    # ==========================================
    # LIMPAR FORMULÁRIO
    # ==========================================
    def _limpar(self):
        self.produto_id = None
        self.produto.clear()
        self.quantidade.clear()
        self.motivo.clear()
        self.tipo.setCurrentIndex(0)

    # ==========================================
    # HELPER DE ERRO
    # ==========================================
    def _exibir_erro(self, response):
        try:
            erro = response.json()["detail"]
        except Exception:
            erro = response.text

        QMessageBox.critical(self, "Erro", erro)
